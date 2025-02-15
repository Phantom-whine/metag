# views.py
import json
import re
import logging
import requests
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import Post
from .serializers import PostSerializer
import google.generativeai as genai
from bs4 import BeautifulSoup
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptAvailable

# Set up logging
logger = logging.getLogger(__name__)
genai.configure(api_key=settings.GEMINI_API_KEY)

# Configure Gemini 1.5 Flash
generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8000,
        "response_mime_type": "text/plain",
    }
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-thinking-exp-1219",
    generation_config=generation_config,
)

chat_session = model.start_chat(history=[])

def summarize_text(text, summary_length=200):
    """
    Summarizes the input text by selecting sentences from the beginning, middle, and end.

    Args:
        text (str): The input text to summarize.
        summary_length (int): The number of sentences to include in the summary.

    Returns:
        str: The summarized text.
    """
    try:
        # Split the text into sentences (assuming sentences are separated by '. ')
        sentences = text.split(". ")

        # Remove empty strings from the list
        sentences = [s.strip() for s in sentences if s.strip()]

        # If there are fewer sentences than the requested summary length, return all sentences
        if len(sentences) <= summary_length:
            return ". ".join(sentences) + "."

        # Calculate the step size to evenly distribute sentences
        step = len(sentences) // summary_length

        # Select sentences from the beginning, middle, and end
        summary_sentences = []
        for i in range(summary_length):
            index = min(
                i * step, len(sentences) - 1
            )  # Ensure we don't go out of bounds
            summary_sentences.append(sentences[index])

        # Join the selected sentences into a summary
        summary = ". ".join(summary_sentences) + "."

        return summary

    except Exception as e:
        logger.error(f"Error in summarize_text: {e}")
        return False

def get_youtube_video_transcript(video_url):
    """
    Fetches the transcript of a YouTube video.

    Args:
        video_url (str): The URL of the YouTube video.

    Returns:
        str: The transcript of the video as a single string, or None if no transcript is available.
    """
    try:
        # Extract the video ID from the URL
        video_id = YouTube(video_url).video_id

        # Fetch the transcript
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)

        # Combine all transcript segments into a single string
        transcript = " ".join([segment["text"] for segment in transcript_list])

        return transcript

    except TranscriptsDisabled as e:
        logger.error(f"Transcripts are disabled for the video: {video_url}")
        return False
    except NoTranscriptAvailable as e:
        logger.error(f"No transcript is available for the video: {video_url}")
        return False
    except Exception as e:
        logger.error(f"An error occurred while fetching the transcript: {e}")
        return False

def extract_content(url):
    """
    Extracts structured content from a webpage URL with focus on headers and main text.

    Args:
        url (str): The URL of the webpage.

    Returns:
        str: Structured text content with headers and main body text.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Send request with timeout and headers
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        
        # Focus on main content areas first
        main_content = soup.find(['article', 'main', 'div.article', 'div.content']) or soup.body
        
        content = []
        
        # Extract headers with hierarchy
        for header in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            level = header.name[1]
            content.append(f"\n{'#' * int(level)} {header.get_text(strip=True)}\n")
        
        # Extract paragraph text with context
        for paragraph in main_content.find_all(['p', 'li']):  # Include list items
            text = paragraph.get_text(strip=True, separator=' ')
            if text:
                content.append(text)
        
        # Add important div text that contains substantial content
        for div in main_content.find_all('div'):
            if len(div.get_text(strip=True)) > 100:  # Arbitrary length threshold
                text = div.get_text(strip=True, separator=' ')
                content.append(text)
        
        # Deduplicate while preserving order
        seen = set()
        clean_content = []
        for item in content:
            if item not in seen:
                seen.add(item)
                clean_content.append(item)
        
        return '\n'.join(clean_content).strip()

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to retrieve webpage: {e}")
        return ""

def extract_json(text_response: str) -> dict:
    """
    Extracts JSON data from Gemini text response containing possible markdown formatting
    
    Args:
        text_response (str): Raw text response from Gemini API
        
    Returns:
        dict: Parsed JSON data
        
    Raises:
        json.JSONDecodeError: If no valid JSON found
    """
    # Try to find JSON in code blocks first
    match = re.search(r'```json\s*(.*?)\s*```', text_response, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    
    # Fallback to direct JSON parse
    return json.loads(text_response)

s_prompt = '''
Sample 1 : 
Deepseek vs GPT

Effective AI models make you question your coding skills.

Why?

Because they're pushing the boundaries of what's possible—

And solving complex problems in ways you never imagined.

They'll generate code for projects you've never attempted, and provide solutions with unprecedented accuracy.

But it's not because they're trying to replace developers—

It's because they're demonstrating potential.

After testing them, you'll realize how powerful AI-assisted coding can become.

Deepseek shows remarkable open-source capabilities.

GPT models offer sophisticated language understanding.

Their strengths differ:
- Deepseek: Strong in code generation
- GPT: Excellent in natural language processing

Each model brings unique advantages to the development landscape.

Some developers will prefer Deepseek's transparency.
Others will lean towards GPT's versatility.

So which AI model will transform your workflow—

An open challenger, or a proven performer?

I know which I'd experiment with.

SAMPLE 2 : So much truth to this.

Ai in medicine is changing everything.

We need to embrace it.

Why this matters:

↳ Ai helps doctors diagnose diseases faster and more accurately.

Quick and correct diagnoses save lives.

↳ Ai can analyze medical data better than humans.

This means better treatment plans for patients.

↳ Ai assists in surgery with precision.

Robotic arms guided by Ai reduce errors in operations.

↳ Ai personalizes patient care.

Tailored treatments improve recovery rates.

The future of healthcare is here and it’s powered by Ai.

Don’t let fear of change stop us from using this incredible tool.



sample 3: GPT or DeepSeek? A question that's been on my mind lately.

I've tested both AI models extensively over the past months. Each time I switch between them, I notice distinct differences in their responses.

GPT feels like talking to a well-trained professional - polite, precise, and sometimes a bit reserved. DeepSeek, on the other hand, comes across as more direct and occasionally more creative in its approach.

The cost difference is significant. GPT can be expensive for regular use, while DeepSeek offers similar capabilities at a lower price point.

But here's what I've learned: the best choice depends entirely on your specific needs.

For creative writing and general conversation, GPT often provides more nuanced responses. For coding and technical tasks, DeepSeek can be surprisingly effective.

I still use both. Some days I prefer GPT's reliability, other days I appreciate DeepSeek's straightforward approach.

What matters 𝐢𝐬𝐧'𝐭 𝐰𝐡𝐢𝐜𝐡 𝐦𝐨𝐝𝐞𝐥 𝐢𝐬 "𝐛𝐞𝐭𝐭𝐞𝐫" - 𝐢𝐭'𝐬 𝐚𝐛𝐨𝐮𝐭 𝐰𝐡𝐢𝐜𝐡 𝐨𝐧𝐞 𝐡𝐞𝐥𝐩𝐬 𝐲𝐨𝐮 𝐚𝐜𝐡𝐢𝐞𝐯𝐞 𝐲𝐨𝐮𝐫 𝐠𝐨𝐚𝐥𝐬 𝐦𝐨𝐫𝐞 𝐞𝐟𝐟𝐞𝐜𝐭𝐢𝐯𝐞𝐥𝐲.

𝐀𝐫𝐞 𝐲𝐨𝐮 𝐮𝐬𝐢𝐧𝐠 𝐞𝐢𝐭𝐡𝐞r 𝐨𝐟 𝐭𝐡𝐞𝐬𝐞 𝐀𝐈 𝐦𝐨𝐝𝐞𝐥𝐬? 𝐈'𝐝 𝐛𝐞 𝐜𝐮𝐫𝐢𝐨𝐮𝐬 𝐭𝐨 𝐡𝐞𝐚𝐫 𝐚𝐛𝐨𝐮𝐭 𝐲𝐨𝐮𝐫 𝐞𝐱𝐩𝐞𝐫𝐢𝐞𝐧𝐜𝐞 𝐰𝐢𝐭𝐡 𝐭𝐡𝐞𝐦.

𝐏.𝐒.: 𝐇𝐚𝐬 𝐚𝐧𝐲𝐨𝐧𝐞 𝐞𝐥𝐬𝐞 𝐧𝐨𝐭𝐢𝐜𝐞𝐝 𝐡𝐨𝐰 𝐪𝐮𝐢𝐜𝐤𝐥𝐲 𝐭𝐡𝐞𝐬𝐞 𝐦𝐨𝐝𝐞𝐥𝐬 𝐚𝐫𝐞 𝐢𝐦𝐩𝐫𝐨𝐯𝐢𝐧𝐠?



SAMPLE 4: 
AI isn't coming for your job - it's already here.

I've seen people panic about AI replacing them. I've also seen others completely ignore its impact.

Both reactions miss the point.

Here's what's really happening:

↳ Creative roles are being enhanced, not replaced
↳ Some industries face more changes than others
↳ New positions are emerging daily
↳ AI is taking over repetitive tasks

I remember when automation hit the manufacturing sector. Workers who adapted thrived. Those who resisted struggled.

The same pattern is happening with AI.

But here's the truth: AI won't replace humans - it will replace humans who don't know how to work with AI.

Think about these questions:

1. Are you learning about AI tools?
2. What new skills are you developing?
3. Have you identified which parts of your job AI could enhance?

The workplace is changing. Fast.

Don't wait for someone to tell you your role is obsolete.

Start exploring AI tools today. Learn how they work. Understand their limitations.

Because the real question isn't if AI will affect your job - it's how you'll use AI to become better at it.

P.S. Share this → help others prepare for the AI revolution 

Write a compelling social media post in an engaging and concise format. The post should:

Start with a bold short (max 5 words), thought-provoking statement or question.
Follow with a short transition sentence that builds intrigue.
Present a numbered or bulleted list of key points with brief explanations.
End with a strong conclusion, takeaway, or call to action.
NOTE: HOOK SHOULD NOT BE MORE THAN 5 WORDS AND SHOULD BE SCROLL STOPPING
NOTE: IT MUST SOUND HUMAN NOT LIKE AI
NOTE: THE POST MUST BE LIKE HUMAN WRITING SO NO GIMICKY WORDS OR PHRASES
NOTE: USE NATURAL LANGUAGE MAKE THE POST ENJOYABLE AND HAS ELEMENTS THAT WILL MAKE READERS READ TO THE END
NOTE: ADD SOME PERSONAL CONTEXT / STORY IN THE POST
NOTE: ALSO YOU CAN ASK SOME QUESTIONS TO THE READERS CAUSING THEM TO THINK BUT BE NATURAL
NOTE: THE SECOND LINE OR SENTENCE SHOULD NOT BE TOO LONG MAX 7 WORDS AND SHOULD GRAB ATTENTION'''

@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def post_get_delete(request, pk):
    """
    Handle retrieval and deletion of individual posts
    
    GET: Returns full post details
    DELETE: Permanently removes the post
    """
    try:
        post = Post.objects.get(pk=pk, user=request.user)
    except Post.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = PostSerializer(post)
        return Response(serializer.data)

    elif request.method == 'DELETE':
        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def post_create_text(request):
    """
    Create a new LinkedIn-style post using AI generation
    
    Expected POST data:
    - topic: Main subject for the post
    - tone: (Optional) Desired writing style (e.g., professional, casual)
    
    Returns created post data with AI-generated content
    """
    try:
        # Build AI prompt with structured requirements
        prompt = f"""
        {s_prompt}
        Ensure the tone is authoritative yet conversational. The topic should be {request.data.get('topic')}, and the post should be formatted similarly to the examples provided also with easy to understand words.
        Tone: {request.data.get('tone')}
        NOTE: NO hashtags
        NOTE: THE CONTENT SHOULD BE THE LINKEDIN POST EACH PARAGRAPH SHOULD BE A <p> TAG AND EACH PARAGRAPH SHOULD HAVE A <br> SPACE BEWEEN THEM
        NOTE: only <p> and <br> should be used no other tag
        NOTE: MAX LENGTH OF 300 words
        ALLOWED TAGS = [P, BR]
        NOTE: NO BOLD TAGS <b> or <strong> or any other text formatting tags in the response
        
        Return JSON format with these keys: 
        ```json{{
            "title": "string",
            "content": "html string only <p> and <br> tags",
            "length": "integer"
        }}```
        """
        
        # Generate content with Gemini 1.5 Flash
        print('-----------4')
        response = chat_session.send_message(prompt)
        generated_data = extract_json(response.text)
        print('-----------4')

        content = generated_data['content']
        print('-----------4')

        if request.data.get('cta'):
            content = f"{generated_data['content']} <br> {request.data.get('cta')}"

        
        # Create and save post
        print('-----------4')
        post = Post.objects.create(
            user=request.user,
            title=generated_data['title'],
            content=content,
            length=generated_data.get('length', len(generated_data['content']))
        )
        
        serializer = PostSerializer(post)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    except json.JSONDecodeError:
        return Response({'error': 'Invalid AI response format'}, 
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except KeyError as e:
        return Response({'error': f'Missing required field: {str(e)}'}, 
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        return Response({'error': str(e)}, 
                       status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def post_create_youtube(request) :
    url = request.data.get('y_url')
    tone = request.data.get('tone')
    cta = request.data.get('cta')

    text = get_youtube_video_transcript(url)
    if not text :
        return Response({'error': 'Could not Fetch youtube video'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        # Build AI prompt with structured requirements
        prompt = f"""
        {s_prompt}
        Ensure the tone is authoritative yet conversational. This is the raw data: {text}, and the post should be formatted similarly to the examples provided also with easy to understand words.
        Tone: {tone}
        NOTE: NO hashtags
        NOTE: THE CONTENT SHOULD BE THE LINKEDIN POST EACH PARAGRAPH SHOULD BE A <p> TAG AND EACH PARAGRAPH SHOULD HAVE A <br> SPACE BEWEEN THEM
        NOTE: only <p> and <br> should be used no other tag
        NOTE: MAX LENGTH OF 300 words
        ALLOWED TAGS = [P, BR]
        NOTE: NO BOLD TAGS <b> or <strong> or any other text formatting tags
        
        NOTE: STRICTLY Return JSON format with these keys: 
        ```json{{
            "title": "string",
            "content": "html string <p> and <br> tags",
            "length": "integer"
        }}```
        """
        
        # Generate content with Gemini 1.5 Flash
        response = chat_session.send_message(prompt)
        generated_data = extract_json(response.text)
        
        # Create and save post
        post = Post.objects.create(
            user=request.user,
            title=generated_data['title'],
            content=generated_data['content'],
            length=generated_data.get('length', len(generated_data['content']))
        )
        
        serializer = PostSerializer(post)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    except json.JSONDecodeError:
        return Response({'error': 'Invalid AI response format'}, 
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except KeyError as e:
        return Response({'error': f'Missing required field: {str(e)}'}, 
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        return Response({'error': str(e)}, 
                       status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def post_create_url(request) :
    url = request.data.get('w_url')
    tone = request.data.get('tone')
    cta = request.data.get('cta')

    text = extract_content(url)
    if not text :
        return Response({'error': 'Could not Fetch youtube video'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        # Build AI prompt with structured requirements
        prompt = f"""
        {s_prompt}
        Ensure the tone is authoritative yet conversational. This is the raw data: {text}, and the post should be formatted similarly to the examples provided also with easy to understand words.
        Tone: {tone}
        NOTE: NO hashtags
        NOTE: THE CONTENT SHOULD BE THE LINKEDIN POST EACH PARAGRAPH SHOULD BE A <p> TAG AND EACH PARAGRAPH SHOULD HAVE A <br> SPACE BEWEEN THEM
        NOTE: only <p> and <br> should be used no other tag
        NOTE: MAX LENGTH OF 300 words
        ALLOWED TAGS = [P, BR]
        NOTE: NO BOLD TAGS <b> or <strong> or any other text formatting tags
        
        Return JSON format with these keys: 
        ```json{{
            "title": "string",
            "content": "html string <p> and <br> tags",
            "length": "integer"
        }}```
        """
        
        # Generate content with Gemini 1.5 Flash
        response = chat_session.send_message(prompt)
        generated_data = extract_json(response.text)
        
        # Create and save post
        post = Post.objects.create(
            user=request.user,
            title=generated_data['title'],
            content=generated_data['content'],
            length=generated_data.get('length', len(generated_data['content']))
        )
        
        serializer = PostSerializer(post)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    except json.JSONDecodeError:
        return Response({'error': 'Invalid AI response format'}, 
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except KeyError as e:
        return Response({'error': f'Missing required field: {str(e)}'}, 
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        return Response({'error': str(e)}, 
                       status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def regenerate_post(request, pk):
    """
    Regenerate an existing post's content using updated AI generation
    
    Args:
        pk: Post ID to regenerate
        
    Returns updated post data with new AI-generated content
    """
    try:
        post = Post.objects.get(pk=pk, user=request.user)
        
        # Build regeneration prompt with existing content
        prompt = f"""
        Improve and regenerate this LinkedIn post while maintaining its core message:
        
        {s_prompt}
        Ensure the tone is authoritative yet conversational. The original Title is {post.title} original content: {post.content}, and the post should be formatted similarly to the examples provided also with easy to understand words.
        NOTE: NO hashtags
        NOTE: THE CONTENT SHOULD BE THE LINKEDIN POST EACH PARAGRAPH SHOULD BE A <p> TAG AND EACH PARAGRAPH SHOULD HAVE A <br> SPACE BEWEEN THEM
        NOTE: only <p> and <br> should be used no other tag
        NOTE: MAX LENGTH OF 300 words
        ALLOWED TAGS = [P, BR]
        NOTE: NO BOLD TAGS <b> or <strong> or any other text formatting tags in the response
        
        Return JSON format with these keys: 
        ```json{{
            "title": "string",
            "content": "html string only <p> and <br> tags",
            "length": "integer"
        }}```
        """
        
        response = model.generate_content(prompt)
        generated_data = extract_json(response.text)
        
        # Update post fields
        post.title = generated_data['title']
        post.content = generated_data['content']
        post.length = generated_data.get('length', len(post.content))
        post.save()
        
        serializer = PostSerializer(post)
        return Response(serializer.data)
    
    except Post.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, 
                       status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_topics(request):
    """
    Generate 3 content topics based on provided field and subfield
    
    Query Parameters:
    - field: Main industry/domain (default: technology)
    - sub_field: Specific area within field (default: AI)
    
    Returns JSON with array of topic suggestions
    """
    try:
        field = request.data.get('field')
        sub_field = request.data.get('sub_field')
        
        prompt = f"""
        Generate 3 evergreen content ideas for {field}/{sub_field} that combine timeless value with viral potential. For each idea:
        - Focus on fundamental questions/problems people always search
        - Include psychological triggers for sharing (curiosity, emotion, surprise)
        - Avoid time-sensitive references
        - Prioritize titles that work across platforms
        - Virality score (50-100) should reflect both shareability and search demand

        Response should be in this format:
            ```json{{
                "topics": [
                    {{"name": "title", "virality": 50 - 100}},
                    {{"name": "title", "virality": 50 - 100}},
                    {{"name": "title", "virality": 50 - 100}}
                ]
            }}```
        """
        response = model.generate_content(prompt)
        generated_data = extract_json(response.text)
        
        return Response({'field': field, 'sub_field': sub_field, 
                        'suggestions': generated_data['topics']})
    
    except Exception as e:
        return Response({'error': str(e)}, 
                       status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def post_list(request):
    """
    List all posts for the authenticated user
    
    Returns array of post objects with basic details
    """
    param_value = request.query_params.get("frame", 'most_recent')
    if param_value == 'most_recent':
        posts = Post.objects.filter(user=request.user).order_by('-created')
    else :
        posts = Post.objects.filter(user=request.user).order_by('created')

    serializer = PostSerializer(posts, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def post_edit(request, id) :
    try:
        post = Post.objects.get(id=id)
        content = request.data.get('content')
        test = remove_html_tags(content)
        
        if not test or len(test) < 30:
            return Response({'msg': 'EMPTY CONTENT'}, status=status.HTTP_400_BAD_REQUEST)
        
        post.content = content
        post.save()

        return Response({'msg': 'Post Saved'}, status=status.HTTP_200_OK)
    except Post.DoesNotExist :
        return Response({'error': 'Post does not exists'}, status=status.HTTP_400_BAD_REQUEST)

def remove_html_tags(text):
    """Remove all HTML tags from a string."""
    return re.sub(r'<[^>]+>', '', text)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def post_save_editor(request) :
    content = request.data.get('content')
    test = remove_html_tags(content)

    if not test or len(test) < 30:
        return Response({'msg': 'EMPTY CONTENT'}, status=status.HTTP_400_BAD_REQUEST)
    
    title = content.split()
    if len(title) > 6 :
        title = ' '.join(title[:8])
    else :
        title = ' '.join(title[:len(title)-1])
    
    post = Post.objects.create(
        content=content,
        title = title,
        user = request.user
    )
    post.save()

    return Response({'msg': 'Post Saved'}, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def post_edit_ai(request) :
    content = request.data.get('content')
    prompt_text = request.data.get('prompt', 'improve')

    prompt = f'''
        MAKE EDIT TO THIS TEXT: {content}
        EDIT: {prompt_text}
        NOTE: IF HAS HTML TAGS IT SHOULD REMAIN THE SAME
        NOTE: MAKE SURE THE RESPONSE SOUNDS HUMAN
        NOTE: IF THE EDIT IS TO EDIT ONLY A PART ONLY EDIT THAT PART AND GIVE THE WHOLE TEXT WITH THE EDITED PART
        NOTE: NO GIMICKS USE EASY TO UNDERTAND WORDS
        NOTE: NO HASHTAGS UNLESS REQUESTED
        NOTE: IF ASKED TO RESTRUCTURE THE RESPONSE IN A NICE FORMAT USING <p> and <br> tags only and maybe numberings and some icons
        NOTE: NO STYLING, NO OTHER TAGS EXCEPT FROM P AND BR AND NO WEIRD FORMATTING JUST TEXT

        THE RESPONSE SHOULD BE IN THIS JSON FORMAT
        ```json{{
            "content": "result here",
            "length": "integer"
            }}
        ```
    '''

    response = model.generate_content(prompt)
    generated_data = extract_json(response.text)

    return Response({"result": generated_data['content']}, status=status.HTTP_200_OK)