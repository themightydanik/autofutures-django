# apps/trading/models.py
from django.db import models
from django.conf import settings
import uuid


class Trade(models.Model):
    """Trading positions (в т.ч. для арбитража спреда)"""

    TRADE_TYPES = [
        ('arbitrage', 'Arbitrage'),
        ('margin', 'Margin'),
        ('spot', 'Spot'),
    ]

    SIDES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
        ('long', 'Long'),
        ('short', 'Short'),
    ]

    STATUSES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trades'
    )

    trade_type = models.CharField(max_length=20, choices=TRADE_TYPES)
    symbol = models.CharField(max_length=20)
    side = models.CharField(max_length=10, choices=SIDES)

    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    exit_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)

    amount = models.DecimalField(max_digits=20, decimal_places=8)
    filled_amount = models.DecimalField(max_digits=20, decimal_places=8, default=0)

    pnl = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    pnl_percent = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    fees = models.DecimalField(max_digits=20, decimal_places=8, default=0)

    status = models.CharField(max_length=20, choices=STATUSES, default='pending')

    # Для арбитража: структура вида
    # {
    #   "exchange_1": {"id": "bybit", "side": "long", "entry": 100.1, ...},
    #   "exchange_2": {"id": "gateio", "side": "short", "entry": 101.3, ...},
    #   "entry_spread": 1.2,
    #   "exit_spread": 0.4,
    #   "funding_fees": {...},
    #   "commissions": {...}
    # }
    exchanges = models.JSONField(null=True, blank=True)

    strategy = models.CharField(max_length=50, null=True, blank=True)

    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trades'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'opened_at']),
            models.Index(fields=['symbol']),
        ]
        ordering = ['-opened_at']

    def __str__(self):
        return f"{self.user.username} - {self.symbol} {self.side} - {self.status}"


class BotLog(models.Model):
    """Bot activity logs"""

    LOG_TYPES = [
        ('info', 'Info'),
        ('success', 'Success'),
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('search', 'Search'),
        ('buy', 'Buy'),
        ('sell', 'Sell'),
        ('transfer', 'Transfer'),
        ('profit', 'Profit'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bot_logs'
    )
    trade = models.ForeignKey(
        Trade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs'
    )
    log_type = models.CharField(max_length=20, choices=LOG_TYPES)
    message = models.TextField()
    details = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bot_logs'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['log_type']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.log_type} - {self.created_at}"


# ===== SPREAD BOT MODELS =====

class UserSymbolSettings(models.Model):
    """
    Персональные настройки для каждой монеты:
    - биржи
    - направление (LONG / SHORT spread)
    - спреды
    - объемы
    - ограничения
    - настройки тиков
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='symbol_settings'
    )

    symbol = models.CharField(max_length=30)  # BTC, ETH...

    # Биржи
    exchange_1 = models.CharField(max_length=50)
    exchange_2 = models.CharField(max_length=50)

    # LONG / SHORT (именно в верхнем регистре — под trade_engine)
    side = models.CharField(
        max_length=10,
        choices=[
            ('LONG', 'Long'),
            ('SHORT', 'Short'),
        ]
    )

    # Спреды для открытия/закрытия (в %)
    open_spread = models.FloatField(default=0.0)
    close_spread = models.FloatField(default=0.0)

    # Объемы ордеров
    # order_size — в монетах
    order_size = models.FloatField(default=0.0)
    # order_size_usdt — в USDT (для удобства смены режима)
    order_size_usdt = models.FloatField(default=0.0)

    # Максимальное количество "ног" (пара позиций)
    max_orders = models.IntegerField(default=0)

    # Stop-флаги
    force_stop = models.BooleanField(default=False)
    total_stop = models.BooleanField(default=False)

    # Количество тиков на графике
    open_ticks = models.IntegerField(default=0)
    close_ticks = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_symbol_settings"
        unique_together = ('user', 'symbol')
        indexes = [
            models.Index(fields=['user', 'symbol']),
        ]

    def __str__(self):
        return f"{self.user.username} – {self.symbol} settings"


class BotState(models.Model):
    """
    Текущее состояние торгового бота по каждой монете.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bot_states'
    )

    symbol = models.CharField(max_length=30)

    # активен ли бот
    is_active = models.BooleanField(default=False)

    # когда стартовал
    started_at = models.DateTimeField(null=True, blank=True)

    # Биржевые данные (обновляются в реальном времени)
    # trade_engine кладёт сюда:
    # - bid/ask/mark по обеим биржам
    # - funding rates
    # - ticks (open/close/real)
    # - pnl, pnl_percent, realized_pnl и т.п.
    data = models.JSONField(default=dict, blank=True)

    # последняя активность
    last_update = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bot_state'
        unique_together = ('user', 'symbol')
        indexes = [
            models.Index(fields=['user', 'symbol']),
        ]

    def __str__(self):
        return f"{self.user.username} – {self.symbol} bot state"
