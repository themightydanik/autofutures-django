# apps/exchanges/serializers.py
from rest_framework import serializers
from .models import ExchangeConnection, Balance


class ExchangeConnectionSerializer(serializers.Serializer):
    """
    Для подключения биржи через API ключи
    """

    exchange_id = serializers.ChoiceField(
        choices=[
            'binance',
            'bybit',
            'gateio',
            'mexc',
            'bingx',
            'bitget',
        ]
    )
    api_key = serializers.CharField()
    secret_key = serializers.CharField(write_only=True)
    passphrase = serializers.CharField(required=False, allow_blank=True)


class BalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Balance
        fields = [
            'exchange_id',
            'currency',
            'free_balance',
            'locked_balance',
            'total_balance',
            'updated_at',
        ]


class ExchangeInfoSerializer(serializers.Serializer):
    """
    Для отдачи базовой инфы о бирже (если нужно на фронт)
    """
    id = serializers.CharField()
    name = serializers.CharField()
    tier = serializers.IntegerField()
    has_spot = serializers.BooleanField()
    has_futures = serializers.BooleanField()
    maker_fee = serializers.FloatField()
    taker_fee = serializers.FloatField()
