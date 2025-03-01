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
from rest_framework.pagination import PageNumberPagination
from django.conf import settings

class CustomPostPaginator(PageNumberPagination):  # Renamed for clarity
    page_size = 9
    page_size_query_param = 'page_size'  # Changed from 'page'
    max_page_size = 9
    page_query_param = 'page'  # Explicitly define page number param

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

def extract_json(text):
    try:
        # Find JSON inside possible Markdown-style AI response
        match = re.search(r'```json\s*({.*?})\s*```', text, re.DOTALL)
        if match:
            text = match.group(1)  # Extract only the JSON part
        
        # Remove any unwanted characters before/after JSON
        text = text.strip().strip('`')

        return json.loads(text)  # Convert to dictionary
    except Exception as e:
        raise ValueError("Invalid JSON format")


s_prompt = '''
# LINKEDIN POST GUIDE: REAL & ENGAGING FORMATS

## MAIN IDEAS
- Share real value in every post
- Mix up how your posts look
- Stick to one main point per post
- Write like you talk, but keep it professional
- Ask real questions people want to answer

HOOK eg (Ads are not Marketing, AI is changing fast, Deepseek Vs Gpt, 3 Marketing Mistakes you should avoid, Will Brics take Over?)

NOTE: THE START OF EVERY POST MUST BE LIKE THIS (
[Hook(max 7 words) start with Capital letter then the rest small letters]
empty(new line (empty space))
[next transition text (max 5 words)]
empty(new line (empty space))
)

CORE MESSAGE STYLES (Pick 1-2)
A. Value Proposition
"The reality? [Honest assessment].

The approach that works? ⬇️"

B. Experience-Based Framework
*"What I've learned about [topic]:
[Element 1] → [Real outcome]
↳ [Practical application]
[Element 2] → [Observed pattern]
↳ [Implementation insight]"*
C. Transformation Story
"[Time frame] of focused effort:
[Starting point]? [Current reality].
[Initial challenge]? [Solution found]."

## POST LAYOUTS (Choose what fits your message)

### 1. ARROW FORMAT (For showing cause-effect eg: How Meditation Boosts Creativity)
```
DECISION FATIGUE IS REAL

Three shifts that changed everything for me:

Clear mind → Better choices
↳ Make big decisions before lunch
↳ Create simple systems for small choices
<line_break here>
Short breaks → Fresh thinking
↳ Take 10 minutes between meetings
↳ Change your space to reset your mind
<line_break here>
Energy planning → Staying focused
↳ Protect your best hours
↳ Work with your natural ups and downs
<line_break here>
Your biggest choices deserve your best thinking.
<line_break here>
How do you stay fresh when making tough calls?
```

### 2. NUMBERED LIST FORMAT (Only use if the post topic is like this eg. [x] things to do))
```
5 WAYS TO DELEGATE BETTER
<line_break here>
That actually help your team grow:
<line_break here>
1. Start with why
   Share the reason, not just the task
   Help people see the bigger picture
<line_break here>
2. Match tasks to people
   Play to strengths
   Think about growth, not just skills
<line_break here>
3. Clear goals, open paths
   Define what success looks like
   Let people find their own way there
<line_break here>
4. Help without taking over
   Be there when needed
   Provide tools, not rescues
<line_break here>
5. Celebrate growth
   Notice the learning
   Praise progress, not just results
<line_break here>
Good delegation isn't about doing less—it's about growing others.
<line_break here>
What's your hardest part of delegating? I'm curious.
```

### 3. THIS vs. THAT FORMAT (Compares two ideas (e.g., "Remote work vs. Office work"))
```
PRODUCTIVITY MYTHS
<line_break here>
What doesn't work vs. What does:
<line_break here>
To-do lists vs. Focus blocks
- Lists feel busy but don't finish things
- Blocks make sure the big stuff gets done
<line_break here>
Clock-watching vs. Energy planning
- Tracking hours drains creativity
- Working with your energy creates flow
<line_break here>
Doing many things vs. Deep work
- Switching tasks wastes nearly half your time
- Focused blocks get real results
<line_break here>
The best system is the one you'll actually stick with.
<line_break here>
What unusual method has helped your productivity?
```

### 4. STORY FORMAT (for personal lessons (e.g., "How I overcame procrastination"))
```
HOW I BEAT BURNOUT
<line_break here>
My journey in 3 parts:
<line_break here>
PART 1: The breaking point
• Working nights and weekends became normal
• Always on my phone, always tired
• Using caffeine instead of rest
<line_break here>
PART 2: The wake-up call
• Realized more hours ≠ better work
• Found my best ideas come when I'm fresh
• Learned that rest makes me more productive
<line_break here>
PART 3: The new way
• Set firm cutoff times
• Told my team when I'm available
• Built rest into my schedule
<line_break here>
This change wasn't quick, but it was worth it.
<line_break here>
What boundary has helped your work life the most?
```

### 5. PROBLEM-SOLUTION FORMAT (For common challenges e.g., "Why people fail at diets and how to succeed")
```
WHY FEEDBACK FAILS
<line_break here>
And how to fix it:
<line_break here>
PROBLEM: Too vague
"Good job" without details
Leaves room for confusion
<line_break here>
FIX: Be specific
Point to exact actions
Connect what they did to what happened
<line_break here>
PROBLEM: Bad timing
Waiting for review season
Saving up issues until they're huge
<line_break here>
FIX: Regular check-ins
Short, casual feedback often
Talk while things are still fresh
<line_break here>
PROBLEM: All criticism, no help
Pointing out what's wrong
Making people defensive
<line_break here>
FIX: Guide, don't just judge
For every problem, offer a next step
Focus on growth, not just fixing

What's your best tip for giving helpful feedback?
```

### 6. ARROW INSIGHT FORMAT (For expert advice e.g. "Top productivity hacks")
```
NEGOTIATION SECRETS
<line_break here>
After hundreds of deals, here's what works:
<line_break here>
Homework → Confidence
↳ Most wins happen before you show up
↳ Know when you'll walk away
<line_break here>
Questions → Finding value
↳ Asking reveals what matters
↳ Understanding needs uncovers hidden wins
<line_break here>
Patience → Better deals
↳ Being OK with silence gets better terms
↳ Rushing looks desperate
<line_break here>
The best negotiators listen more than they talk.
<line_break here>
What's your go-to negotiation trick?
```

### 7. BULLET POINT FORMAT (For quick tips eg Habits for sharper focus)
```
BETTER MEETINGS

Three changes that cut our meeting time in half:
<line_break here>
• Start with a clear goal
  Know what success looks like before you begin
<line_break here>
• Send prep work early
  Good homework leads to good talk time
<line_break here>
• Create, then evaluate
  Don't judge ideas while they're still forming
<line_break here>
These simple shifts saved us hours while getting better results.
<line_break here>
Which one would help your meetings the most?
```

### 8. PLAIN TEXT STORY (For personal reflections)
```
THE ADVICE I WISH I'D GOTTEN EARLIER

I was stuck. Working hard but not feeling right about it.

Everyone told me: work harder, meet more people, learn new skills.

It all made sense, but nothing changed.
<line_break here>
Then someone asked me something different: "What problems do you actually enjoy solving?"

Not what I was good at. Not what paid well. But what energized me even when it was hard.

That question changed everything.

I realized I was climbing the wrong ladder. Good at work that drained me instead of filling me up.

The change wasn't overnight, but that question started me on a new path.

Now I ask everyone I mentor the same thing.

What problems do you actually enjoy solving?
```

## WAYS TO END YOUR POST

### QUESTIONS TO ASK
```
What's been your experience with this?
```

```
Which of these ideas clicks most with you?
```

```
How have you handled this in your work?
```

```
What would you add based on your experience?
```

### INVITATIONS TO ACT
```
Try just one of these ideas this week. I'd love to hear what happens.
```

```
Think about which of these patterns might be showing up in your team.
```

```
Share your biggest takeaway if this sparked any new thoughts.
```

### THOUGHTFUL ENDINGS
```
Take a moment: Which of these shows up most in your work?
```

```
Think about your last tough project: Which idea here could have helped?
```

```
Consider where you might be following the crowd when a different approach could work better.
```
RULES:

Vary your approach between posts to maintain freshness
Content before format - ensure valuable insights drive each section
Use ↳ with four leading spaces for visual indentation (4 SPACES)
Related lines should not have any space between them
Focus on genuine experiences and practical wisdom
Avoid industry jargon and buzzwords
Write conversationally but professionally
Each post should deliver one clear, valuable insight
Replace ALL [brackets] with appropriate text
Test for authenticity: Would you share this advice one-on-one?

## KEEPING IT REAL
- Write what you know, not just theories
- Include real examples that show you've been there
- Share practical wisdom, not generic advice
- Ask yourself: "Would I say this to someone face-to-face?"
- Focus on helping, not going viral

Write a compelling social media post in an engaging and concise format. The post should:

Start with a bold short (max 5 words), thought-provoking statement or question.
Follow with a short transition sentence that builds intrigue (max 5 words).
Present a numbered or bulleted list of key points with brief explanations (WHEN NEEDED).
End with a strong conclusion, takeaway, or call to action.
NOTE: HOOK SHOULD NOT BE MORE THAN 8 WORDS AND SHOULD BE SCROLL STOPPING
NOTE: IT MUST SOUND HUMAN NOT LIKE AI
NOTE: THE POST MUST BE LIKE HUMAN WRITING SO NO GIMICKY WORDS OR PHRASES
NOTE: USE NATURAL LANGUAGE MAKE THE POST ENJOYABLE AND HAS ELEMENTS THAT WILL MAKE READERS READ TO THE END
NOTE: ADD SOME PERSONAL CONTEXT / STORY IN THE POST
NOTE: ALSO YOU CAN ASK SOME QUESTIONS TO THE READERS CAUSING THEM TO THINK BUT BE NATURAL
NOTE: THE SECOND LINE OR SENTENCE SHOULD NOT BE TOO LONG MAX 7 WORDS AND SHOULD GRAB ATTENTION
NOTE: THE POST MUST HAVE ALOT OF CONTEXT NOT VERY SHORT WITH NO CONTEXT
NOTE: THE FIRST AND SECOND LINE NO MORE THAN 58WORDS
NOTE: NO BOLDED TEXT NO <B>, <STRONG> TAGS
NOTE: THE THIRD SENTENCE SHOULD BE SHORT MAX (6 WORDS)
'''

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
    
def remove_brackets_inside_html(text):
    return re.sub(r"\[(.*?)\]", r"\1", text)

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
        NOTE: only <p> and <br> should be used
        NOTE: MIN LENGTH (90 WORDS) MAX LENGTH (190) words
        ALLOWED TAGS = [P, BR]
        
        Return JSON format with these keys: 
        ```json{{
            "title": "string should be short max 4 words",
            "content": "html string only <p> and <br> tags",
            "length": "integer"
        }}```
        """
        
        # Generate content with Gemini 1.5 Flash
        response = chat_session.send_message(prompt)
        generated_data = extract_json(response.text)

        content = generated_data['content']
        content = content.replace('[', '')
        content = content.replace(']', '')

        if request.data.get('cta'):
            content = f"{generated_data['content']} <br> {request.data.get('cta')}"

        
        # Create and save post
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


def get_youtube_transcript(url, api_key):
    """
    Fetches the transcript from the YouTube API and removes the 'text' key from the response.

    Args:
        url (str): The YouTube video URL.
        api_key (str): The API key for authentication.

    Returns:
        dict: The API response with 'text' keys removed from the 'content' list.
    """
    api_url = f"https://api.supadata.ai/v1/youtube/transcript?url={url}&text=true"
    headers = {"x-api-key": api_key}

    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()

        # Remove the 'text' key from each dictionary in the 'content' list
        if "content" in data:
            return data['content']


    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def get_keypoints(source) :
    prompt = f'''
        Analyze this text: {source} and give me the key points
        NOTE: STRICTLY Return JSON format with these keys: 
        ```json{{
            "keypoints": "keypoints here",
        }}```
    '''

    response = chat_session.send_message(prompt)
    generated_data = extract_json(response.text)

    return generated_data['keypoints']

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def post_create_youtube(request) :
    url = request.data.get('y_url')
    tone = request.data.get('tone')
    cta = request.data.get('cta')

    text = get_youtube_transcript(url, settings.SUPA_DATA_KEY)
    if not text :
        return Response({'error': 'Could not Fetch youtube video'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        # Build AI prompt with structured requirements
        prompt = f"""
        {s_prompt}
        Ensure the tone is authoritative yet conversational. This is the Youtube Video Transcript: {text}, and the post should be formatted similarly to the examples provided also with easy to understand words.
        NOTE: THE PST MUST CONTAIN KEY POINTS FROM THE YOUTUBE VIDEO
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
        content = generated_data['content']
        content = content.replace('[', '')
        content = content.replace(']', '')
        
        # Create and save post
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
        content = generated_data['content']
        content = content.replace('[', '')
        content = content.replace(']', '')
        
        # Create and save post
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
        Improve and regenerate this LinkedIn post while maintaining its core message and Layout:

        NOTE: NO BOLDED TEXT
        Ensure the tone should not chnage yet conversational. The original Title is {post.title} original content: {post.content}, and the post should be formatted similarly to the examples provided also with easy to understand words.
        NOTE: NO hashtags
        NOTE: THE CONTENT SHOULD BE THE LINKEDIN POST EACH PARAGRAPH SHOULD BE A <p> TAG AND EACH PARAGRAPH SHOULD HAVE A <br> SPACE BEWEEN THEM
        NOTE: only <p> and <br> should be used no other tag
        NOTE: MAX LENGTH OF 300 words
        ALLOWED TAGS = [P, BR]
        NOTE: NO BOLD TAGS <b> or <strong> or any other text formatting tags in the response
        NOTE: THE CTA SHOULD NEVER CHANGE IT SHOULD BE THE SAME
        
        Return JSON format with these keys: 
        ```json{{
            "title": "string max 5 words",
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
    else:
        posts = Post.objects.filter(user=request.user).order_by('created')

    paginator = CustomPostPaginator()  # Use your custom class
    paginated = paginator.paginate_queryset(posts, request)
    
    serializer_inst = PostSerializer(paginated, many=True)
    return paginator.get_paginated_response(serializer_inst.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def post_edit(request, id) :
    try:
        post = Post.objects.get(id=id)
        content = request.data.get('content')
        test = remove_html_tags(content)
        
        if not test or len(test) < 30:
            return Response({'msg': 'EMPTY CONTENT'}, status=status.HTTP_400_BAD_REQUEST)
        

        if content != post.content :
            post.edited = True

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
    if len(title) > 5 :
        title = ' '.join(title[:5])
    else :
        title = ' '.join(title[:len(title)-1])
    
    post = Post.objects.create(
        content=content,
        title = title,
        user = request.user
    )
    if content != post.content :
        post.edited = True
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

        THE RESPONSE SHOULD BE IN THIS JSON FORMAT
        ```json{{
            "content": "result here (valid for json content)",
            "length": "integer"
            }}
        ```
    '''

    prompt = prompt.replace('<!---->', '')
    response = model.generate_content(prompt)
    try:
        generated_data = extract_json(response.text)
    except:
        try:
            fallback = json.loads(response.text)
            return Response({"result": fallback['content']}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': 'Could no generate'}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"result": generated_data['content']}, status=status.HTTP_200_OK)