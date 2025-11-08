# ===== apps/users/models.py =====
from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

class User(AbstractUser):
    """Custom User model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, null=True, blank=True)
    google_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.username

class UserSettings(models.Model):
    """User trading settings"""
    TRADE_TYPES = [
        ('margin', 'Margin Trading'),
        ('arbitrage', 'Arbitrage'),
    ]
    
    STRATEGIES = [
        ('breakout', 'Breakout'),
        ('retest', 'Retest'),
        ('trend', 'Trend Following'),
        ('inter-exchange', 'Inter-exchange Arbitrage'),
        ('triangular', 'Triangular Arbitrage'),
        ('intra-exchange', 'Intra-exchange Arbitrage'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings')
    trade_type = models.CharField(max_length=20, choices=TRADE_TYPES, null=True, blank=True)
    strategy = models.CharField(max_length=50, choices=STRATEGIES, null=True, blank=True)
    telegram_notifications = models.BooleanField(default=False)
    telegram_chat_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_settings'
        verbose_name = 'User Settings'
        verbose_name_plural = 'User Settings'
    
    def __str__(self):
        return f"{self.user.username}'s settings"
