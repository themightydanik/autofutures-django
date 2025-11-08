# ===== apps/trading/serializers.py =====
from rest_framework import serializers
from .models import Trade, BotLog

class TradeSerializer(serializers.ModelSerializer):
    coin = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Trade
        fields = ['id', 'coin', 'trade_type', 'entry_price', 'exit_price', 'current_price', 
                  'amount', 'pnl', 'pnl_percent', 'status', 'exchanges', 'opened_at', 'closed_at']
    
    def get_coin(self, obj):
        return obj.symbol
    
    def get_current_price(self, obj):
        return float(obj.entry_price)  # TODO: Get real current price

class BotLogSerializer(serializers.ModelSerializer):
    time = serializers.SerializerMethodField()
    type = serializers.CharField(source='log_type')
    
    class Meta:
        model = BotLog
        fields = ['id', 'time', 'type', 'log_type', 'message', 'created_at']
    
    def get_time(self, obj):
        return obj.created_at.strftime('%H:%M:%S')

class TradeParamsSerializer(serializers.Serializer):
    coin = serializers.CharField(default='BTC')
    side = serializers.ChoiceField(choices=['LONG', 'SHORT'], default='LONG')
    order_size = serializers.FloatField(default=100.0, min_value=10.0)
    stop_loss = serializers.FloatField(default=2.0, min_value=0.0, max_value=100.0)
    take_profit = serializers.FloatField(default=5.0, min_value=0.0, max_value=100.0)
    frequency = serializers.ChoiceField(choices=['low', 'medium', 'high'], default='medium')
    max_trades = serializers.IntegerField(default=10, min_value=1, max_value=100)
    min_profit_threshold = serializers.FloatField(default=0.1, min_value=0.0)
