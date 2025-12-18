# ===== apps/users/views.py =====
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from .models import UserSettings
from .serializers import (
    UserSerializer, UserRegisterSerializer, UserLoginSerializer,
    GoogleAuthSerializer, UserSettingsSerializer
)
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """Register new user"""
    serializer = UserRegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        with transaction.atomic():
            # Check if user exists
            if User.objects.filter(username=serializer.validated_data['username']).exists():
                return Response({'detail': 'Username already exists'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Create user
            user = User.objects.create_user(
                username=serializer.validated_data['username'],
                password=serializer.validated_data['password'],
                email=serializer.validated_data.get('email', '')
            )
            
            # Create settings
            UserSettings.objects.create(user=user)
            
            # Create token
            token, _ = Token.objects.get_or_create(user=user)
            
            return Response({
                'success': True,
                'user_id': str(user.id),
                'username': user.username,
                'email': user.email,
                'token': token.key
            }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """Login user"""
    serializer = UserLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    user = authenticate(
        username=serializer.validated_data['username'],
        password=serializer.validated_data['password']
    )
    
    if not user:
        return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    
    if not user.is_active:
        return Response({'detail': 'Account is disabled'}, status=status.HTTP_401_UNAUTHORIZED)
    
    # Update last login
    user.save(update_fields=['last_login'])
    
    # Get or create token
    token, _ = Token.objects.get_or_create(user=user)
    
    return Response({
        'success': True,
        'user_id': str(user.id),
        'username': user.username,
        'email': user.email,
        'is_admin': user.is_staff,
        'token': token.key
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def google_login(request):
    """Google OAuth login"""
    serializer = GoogleAuthSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # TODO: Implement Google token verification
    # from google.oauth2 import id_token
    # from google.auth.transport import requests
    
    return Response({'detail': 'Google OAuth not implemented yet'}, status=status.HTTP_501_NOT_IMPLEMENTED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """Logout user"""
    try:
        request.user.auth_token.delete()
        return Response({'success': True})
    except Exception as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile(request):
    """Get user profile"""
    serializer = UserSerializer(request.user)
    return Response(serializer.data)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def user_settings(request):
    """Get or update user settings"""
    settings, _ = UserSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'GET':
        serializer = UserSettingsSerializer(settings)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = UserSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'success': True})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

