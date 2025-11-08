# ===== apps/users/admin.py =====
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserSettings

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'is_staff', 'is_active', 'created_at']
    list_filter = ['is_staff', 'is_active', 'created_at']
    search_fields = ['username', 'email']
    ordering = ['-created_at']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('google_id', 'last_login_ip')}),
    )

@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'trade_type', 'strategy', 'telegram_notifications', 'updated_at']
    list_filter = ['trade_type', 'strategy', 'telegram_notifications']
    search_fields = ['user__username']
    raw_id_fields = ['user']
