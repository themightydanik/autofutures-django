# ===== apps/trading/admin.py =====
from django.contrib import admin
from .models import Trade, BotLog

@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ['user', 'symbol', 'trade_type', 'side', 'status', 'pnl', 'opened_at', 'closed_at']
    list_filter = ['trade_type', 'status', 'opened_at']
    search_fields = ['user__username', 'symbol']
    raw_id_fields = ['user']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(BotLog)
class BotLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'log_type', 'message', 'created_at']
    list_filter = ['log_type', 'created_at']
    search_fields = ['user__username', 'message']
    raw_id_fields = ['user', 'trade']
    readonly_fields = ['created_at']
