# ===== apps/analytics/admin.py =====
from django.contrib import admin
from .models import PnLHistory

@admin.register(PnLHistory)
class PnLHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'timestamp', 'pnl', 'pnl_percent', 'cumulative_pnl', 'trades_count']
    list_filter = ['timestamp']
    search_fields = ['user__username']
    raw_id_fields = ['user']
