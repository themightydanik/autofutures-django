# ===== apps/trading/views.py =====
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.db import transaction
from django.utils import timezone

from .models import (
    Trade,
    BotLog,
    UserSymbolSettings,
    BotState,
)

from .serializers import (
    TradeSerializer,
    BotLogSerializer,
    UserSymbolSettingsSerializer,
    BotStateSerializer,
    FullSymbolStateSerializer,
)

from .trade_engine import trade_engine   # новый движок будет под новую архитектуру

import logging
logger = logging.getLogger(__name__)


# ============================================================
# 1.  SETTINGS LOGIC — SAVE / GET USER SETTINGS FOR SYMBOL
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_symbol_settings(request, symbol):
    """
    Получить сохранённые настройки карточки для монеты.
    """
    try:
        settings = UserSymbolSettings.objects.get(user=request.user, symbol=symbol.upper())
        serializer = UserSymbolSettingsSerializer(settings)
        return Response(serializer.data)
    except UserSymbolSettings.DoesNotExist:
        # Вернуть пустые дефолтные значения
        return Response({
            "symbol": symbol.upper(),
            "message": "No settings defined yet"
        }, status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_symbol_settings(request, symbol):
    """
    Сохранить настройки карточки монеты.
    """
    symbol = symbol.upper()

    try:
        with transaction.atomic():
            obj, _ = UserSymbolSettings.objects.update_or_create(
                user=request.user,
                symbol=symbol,
                defaults=request.data
            )
            return Response({"success": True})
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ============================================================
# 2. BOT START / STOP / STATUS
# ============================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_bot(request, symbol):
    """
    Запускаем бота для монеты (входит в режим ожидания подходящего спреда).
    """
    symbol = symbol.upper()

    try:
        # Создаем / обновляем состояние бота
        bot, _ = BotState.objects.update_or_create(
            user=request.user,
            symbol=symbol,
            defaults={
                "is_active": True,
                "started_at": timezone.now(),
                "last_update": timezone.now(),
                "data": {}
            }
        )

        # Сообщаем движку
        trade_engine.start(symbol=symbol, user=request.user)

        return Response({"success": True, "status": "started"})
    except Exception as e:
        logger.error(f"Bot start failed: {e}")
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_bot(request, symbol):
    symbol = symbol.upper()

    try:
        BotState.objects.filter(user=request.user, symbol=symbol).update(
            is_active=False,
            last_update=timezone.now()
        )

        trade_engine.stop(symbol=symbol, user=request.user)

        return Response({"success": True, "status": "stopped"})
    except Exception as e:
        logger.error(f"Bot stop failed: {e}")
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_bot_state(request, symbol):
    symbol = symbol.upper()

    try:
        settings = UserSymbolSettings.objects.get(user=request.user, symbol=symbol)
        bot_state = BotState.objects.filter(user=request.user, symbol=symbol).first()

        combined = FullSymbolStateSerializer({
            "settings": settings,
            "bot_state": bot_state
        })

        return Response(combined.data)

    except UserSymbolSettings.DoesNotExist:
        return Response({"detail": "No settings found"}, status=404)


# ============================================================
# 3.  HISTORICAL TRADES AND LOGS
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_trades(request):
    trades = Trade.objects.filter(user=request.user, status='active')
    return Response(TradeSerializer(trades, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_trade_history(request):
    limit = int(request.query_params.get('limit', 100))
    trades = Trade.objects.filter(user=request.user, status='completed')[:limit]
    return Response(TradeSerializer(trades, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_bot_logs(request):
    limit = int(request.query_params.get('limit', 50))
    logs = BotLog.objects.filter(user=request.user)[:limit]
    return Response({
        "logs": BotLogSerializer(logs, many=True).data
    })
