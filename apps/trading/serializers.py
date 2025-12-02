# ===== apps/trading/serializers.py =====
from rest_framework import serializers
from .models import Trade, BotLog, UserSymbolSettings, BotState


# ==========================
# EXISTING SERIALIZERS
# ==========================

class TradeSerializer(serializers.ModelSerializer):
    coin = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Trade
        fields = [
            'id', 'coin', 'trade_type',
            'entry_price', 'exit_price', 'current_price',
            'amount', 'pnl', 'pnl_percent',
            'status', 'exchanges', 'opened_at', 'closed_at'
        ]
    
    def get_coin(self, obj):
        return obj.symbol
    
    def get_current_price(self, obj):
        return float(obj.entry_price)  # TODO — подключим real price позже


class BotLogSerializer(serializers.ModelSerializer):
    time = serializers.SerializerMethodField()
    type = serializers.CharField(source='log_type')
    
    class Meta:
        model = BotLog
        fields = [
            'id', 'time', 'type', 'log_type',
            'message', 'created_at'
        ]
    
    def get_time(self, obj):
        return obj.created_at.strftime('%H:%M:%S')



# ==========================
# NEW SERIALIZERS
# ==========================

class UserSymbolSettingsSerializer(serializers.ModelSerializer):
    """
    Сериализация настроек карточки для каждой монеты.
    """

    class Meta:
        model = UserSymbolSettings
        fields = [
            'id', 'symbol', 'exchange_1', 'exchange_2', 'side',
            'open_spread', 'close_spread',
            'order_size', 'max_orders',
            'force_stop', 'total_stop',
            'open_ticks', 'close_ticks',
            'created_at', 'updated_at'
        ]


class BotStateSerializer(serializers.ModelSerializer):
    """
    Состояние бота + биржевые данные.
    """

    class Meta:
        model = BotState
        fields = [
            'id', 'symbol', 'is_active',
            'started_at', 'data', 'last_update'
        ]



# ==========================
# COMBINED RESPONSE SERIALIZER
# ==========================

class FullSymbolStateSerializer(serializers.Serializer):
    """
    Сборка данных карточки:
    - настройки
    - состояние бота
    """

    settings = UserSymbolSettingsSerializer()
    bot_state = BotStateSerializer(allow_null=True)
