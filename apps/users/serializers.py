# ===== apps/users/serializers.py =====
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UserSettings

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_staff', 'created_at']
        read_only_fields = ['id', 'created_at']

class UserRegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=6)
    email = serializers.EmailField(required=False, allow_blank=True)

class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

class GoogleAuthSerializer(serializers.Serializer):
    token = serializers.CharField()

class UserSettingsSerializer(serializers.ModelSerializer):
    exchanges = serializers.SerializerMethodField()
    
    class Meta:
        model = UserSettings
        fields = ['trade_type', 'strategy', 'exchanges', 'telegram_notifications', 'telegram_chat_id']
    
    def get_exchanges(self, obj):
        return [conn.exchange_id for conn in obj.user.exchange_connections.filter(is_active=True)]
