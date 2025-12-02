# ===== apps/trading/serializers.py =====
from rest_framework import serializers
from .models import (
    Trade,
    BotLog,
    UserSymbolSettings,
    BotState
)

# ============================================================
# 1.  USER SYMBOL SETTINGS (Карточка настроек монеты)
# ============================================================

class UserSymbolSettingsSerializer(serializers.ModelSerializer):
    """
    Настройки, которые пользователь вводит в карточке для конкретной монеты.
    Хранятся в таблице UserSymbolSettings.
    """
    class Meta:
        model = UserSymbolSettings
        fields = [
            "symbol",
            "exchange_1",
            "exchange_2",
            "side",

            "open_spread",
            "close_spread",

            "order_size",
            "order_size_usdt",
            "max_orders",

            "open_ticks",
            "close_ticks",

            "force_stop",
            "total_stop",
        ]


# ============================================================
# 2.  BOT STATE (реальное состояние бота)
# ============================================================

class BotStateSerializer(serializers.ModelSerializer):
    """
    Статус бота, его прогресс, состояние торговли в реальном времени.
    """
    class Meta:
        model = BotState
        fields = [
            "symbol",
            "is_active",
            "started_at",
            "last_update",
            "data",
        ]


# ============================================================
# 3.  FULL STATE FOR FRONTEND (settings + bot state)
# ============================================================

class FullSymbolStateSerializer(serializers.Serializer):
    """
    Возвращает ОДИН JSON из:
    - сохранённых настроек монеты
    - состояния бота
    Используется во views.py → get_bot_state
    """

    settings = UserSymbolSettingsSerializer()
    bot_state = BotStateSerializer(allow_null=True)


# ============================================================
# 4. TRADES
# ============================================================

class TradeSerializer(serializers.ModelSerializer):
    coin = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()

    class Meta:
        model = Trade
        fields = [
            "id",
            "coin",
            "trade_type",
            "entry_price",
            "exit_price",
            "current_price",
            "amount",
            "pnl",
            "pnl_percent",
            "status",
            "exchanges",
            "opened_at",
            "closed_at",
        ]

    def get_coin(self, obj):
        return obj.symbol

    def get_current_price(self, obj):
        # позже можно подключить реальную цену
        return float(obj.entry_price)


# ============================================================
# 5. LOGS
# ============================================================

class BotLogSerializer(serializers.ModelSerializer):
    time = serializers.SerializerMethodField()
    type = serializers.CharField(source="log_type")

    class Meta:
        model = BotLog
        fields = ["id", "time", "type", "log_type", "message", "created_at"]

    def get_time(self, obj):
        return obj.created_at.strftime("%H:%M:%S")


# ============================================================
# 6. Универсальный сериализатор для сохранения параметров бота
#    (если понадобится)
# ============================================================

class BotControlParamsSerializer(serializers.Serializer):
    side = serializers.ChoiceField(choices=["LONG", "SHORT"])
    order_size = serializers.FloatField(min_value=0.001)
    max_orders = serializers.IntegerField(min_value=1)
    open_spread = serializers.FloatField()
    close_spread = serializers.FloatField()
    exchange_1 = serializers.CharField()
    exchange_2 = serializers.CharField()
