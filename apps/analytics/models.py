# ===== apps/analytics/models.py =====
from django.db import models
from django.conf import settings
import uuid

class PnLHistory(models.Model):
    """PnL history for charts"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pnl_history')
    timestamp = models.DateTimeField()
    pnl = models.DecimalField(max_digits=20, decimal_places=8)
    pnl_percent = models.DecimalField(max_digits=10, decimal_places=4)
    cumulative_pnl = models.DecimalField(max_digits=20, decimal_places=8)
    trades_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'pnl_history'
        indexes = [
            models.Index(fields=['user', 'timestamp']),
        ]
        ordering = ['-timestamp']
