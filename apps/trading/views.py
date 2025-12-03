# ===== apps/trading/views.py =====
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.db import transaction
from django.utils import timezone

import logging

from .models import (
    Trade,
    BotLog,
    UserSymbolSettings,
    BotState
)

from .serializers import (
    TradeSerializer,
    BotLogSerializer,
    UserSymbolSettingsSerializer,
    FullSymbolStateSerializer,
)

from .trade_engine import trade_engine

logger = logging.getLogger(__name__)


# ============================================================
# 1. USER SETTINGS FOR SYMBOL
# ============================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_symbol_settings(request, symbol):
    symbol = symbol.upper()

    settings = UserSymbolSettings.objects.filter(
        user=request.user, symbol=symbol
    ).first()

    if not settings:
        return Response(
            {"symbol": symbol, "message": "No settings defined yet"},
            status=status.HTTP_204_NO_CONTENT
        )

    return Response(UserSymbolSettingsSerializer(settings).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def save_symbol_settings(request, symbol):
    symbol = symbol.upper()

    serializer = UserSymbolSettingsSerializer(
        data=request.data,
        partial=True
    )

    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    validated = serializer.validated_data

    try:
        with transaction.atomic():
            UserSymbolSettings.objects.update_or_create(
                user=request.user,
                symbol=symbol,
                defaults=validated
            )

        return Response({"success": True})

    except Exception as e:
        logger.error(f"Error saving symbol settings: {e}")
        return Response({"detail": str(e)}, status=400)


# ============================================================
# 2. BOT START / STOP / STATUS — ASYNC
# ============================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
async def start_bot(request, symbol):
    symbol = symbol.upper()

    try:
        # Обновляем состояние в БД
        BotState.objects.update_or_create(
            user=request.user,
            symbol=symbol,
            defaults={
                "is_active": True,
                "started_at": timezone.now(),
                "last_update": timezone.now(),
                "data": {}
            }
        )

        # <-- ВАЖНО: async запуск -->
        await trade_engine.start(symbol, request.user)

        return Response({"success": True, "status": "started"})

    except Exception as e:
        logger.error(f"Bot start failed: {e}")
        return Response({"detail": str(e)}, status=400)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
async def stop_bot(request, symbol):
    symbol = symbol.upper()

    try:
        BotState.objects.filter(
            user=request.user,
            symbol=symbol
        ).update(is_active=False, last_update=timezone.now())

        # <-- ВАЖНО: async остановка -->
        await trade_engine.stop(symbol, request.user)

        return Response({"success": True, "status": "stopped"})

    except Exception as e:
        logger.error(f"Bot stop failed: {e}")
        return Response({"detail": str(e)}, status=400)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_bot_state(request, symbol):
    symbol = symbol.upper()

    settings = UserSymbolSettings.objects.filter(
        user=request.user, symbol=symbol
    ).first()

    if not settings:
        return Response({"detail": "No settings found"}, status=404)

    bot_state = BotState.objects.filter(
        user=request.user, symbol=symbol
    ).first()

    combined = {
        "settings": settings,
        "bot_state": bot_state
    }

    return Response(FullSymbolStateSerializer(combined).data)


# ============================================================
# 3. TRADES AND LOGS
# ============================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_active_trades(request):
    trades = Trade.objects.filter(
        user=request.user,
        status="active"
    ).order_by("-opened_at")
    return Response(TradeSerializer(trades, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_trade_history(request):
    limit = int(request.query_params.get("limit", 100))
    trades = Trade.objects.filter(
        user=request.user,
        status="completed"
    ).order_by("-closed_at")[:limit]
    return Response(TradeSerializer(trades, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_bot_logs(request):
    limit = int(request.query_params.get("limit", 50))
    logs = BotLog.objects.filter(user=request.user).order_by("-created_at")[:limit]
    return Response({"logs": BotLogSerializer(logs, many=True).data})
