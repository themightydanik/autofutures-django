# ===== apps/exchanges/admin.py =====
from django.contrib import admin
from .models import ExchangeConnection, Balance

@admin.register(ExchangeConnection)
class ExchangeConnectionAdmin(admin.ModelAdmin):
    list_display = ['user', 'exchange_id', 'is_active', 'last_sync', 'created_at']
    list_filter = ['exchange_id', 'is_active', 'created_at']
    search_fields = ['user__username', 'exchange_id']
    raw_id_fields = ['user']
    readonly_fields = ['api_key_encrypted', 'secret_key_encrypted']

@admin.register(Balance)
class BalanceAdmin(admin.ModelAdmin):
    list_display = ['user', 'exchange_id', 'currency', 'total_balance', 'updated_at']
    list_filter = ['exchange_id', 'currency', 'updated_at']
    search_fields = ['user__username']
    raw_id_fields = ['user']
