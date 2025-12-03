# apps/exchanges/models.py
from django.db import models
from django.conf import settings
import uuid


class ExchangeConnection(models.Model):
    """User's exchange API connections"""

    EXCHANGES = [
        ('binance', 'Binance'),
        ('bybit', 'Bybit'),
        ('gateio', 'Gate.io'),
        ('mexc', 'MEXC'),
        ('bingx', 'BingX'),
        ('bitget', 'Bitget'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exchange_connections'
    )

    exchange_id = models.CharField(max_length=20, choices=EXCHANGES)

    # зашифрованные ключи
    api_key_encrypted = models.TextField()
    secret_key_encrypted = models.TextField()
    passphrase_encrypted = models.TextField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    last_sync = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'exchange_connections'
        unique_together = ['user', 'exchange_id']
        indexes = [
            models.Index(fields=['user', 'exchange_id']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.exchange_id}"


class Balance(models.Model):
    """User balances on exchanges"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='balances'
    )

    exchange_id = models.CharField(max_length=20)
    currency = models.CharField(max_length=10)

    free_balance = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    locked_balance = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    total_balance = models.DecimalField(max_digits=20, decimal_places=8, default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'balances'
        unique_together = ['user', 'exchange_id', 'currency']
        indexes = [
            models.Index(fields=['user', 'exchange_id']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.exchange_id} - {self.currency}"
