from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token
from google.auth.transport import requests
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework.permissions import IsAuthenticated

User = get_user_model()

@api_view(["POST"])
def continue_with_google(request):
    google_token = request.data.get("token")
    if not google_token:
        return Response(
            {"error": "Google token is required"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Verify the Google token
        idinfo = id_token.verify_oauth2_token(
            google_token, requests.Request(), settings.GOOGLE_CLIENT_ID
        )

        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Wrong issuer.")

        # Get user info from the verified token
        user_email = idinfo["email"]
        user_name = idinfo.get("name", "")
        profile_picture = idinfo.get("picture", "")  # Get profile picture

        # Get or create user
        user, created = User.objects.get_or_create(
            email=user_email, defaults={"username": user_email.split('@')[0]},
            fullname=user_name
        )

        if created:
            # Additional user initialization logic if needed
            user.is_active = True
            user.save()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "profile": profile_picture,
                "message": "User created" if created else "User logged in",
            }
        )

    except ValueError:
        return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_details(request) :
    user = request.user
    data = {
        'fullname': user.fullname,
        'username': user.username,
        'email': user.email
    }

    return Response(data, status=status.HTTP_200_OK)