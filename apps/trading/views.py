# ===== apps/trading/views.py =====

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from django.utils import timezone
from django.db import transaction

import logging

from .models import Trade, BotLog, UserSymbolSettings, BotState
from .serializers import TradeSerializer, BotLogSerializer
from .trade_engine import trade_engine

logger = logging.getLogger(__name__)


# ============================================================
# SYMBOL FULL STATE (MAIN ENDPOINT FOR DASHBOARD)
# ============================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_symbol_state(request, symbol):
    symbol = symbol.upper()
    user = request.user

    settings, _ = UserSymbolSettings.objects.get_or_create(
        user=user,
        symbol=symbol,
        defaults={
            "trade_type": "futures",
            "strategy": "spread",
            "base_order_size": 10,
            "open_spread": 0.2,
            "close_spread": 0.05,
        }
    )

    bot_state, _ = BotState.objects.get_or_create(
        user=user,
        symbol=symbol,
        defaults={
            "is_active": False,
            "data": {},
            "last_update": timezone.now(),
        }
    )

    return Response({
        "symbol": symbol,
        "is_active": bot_state.is_active,
        "started_at": bot_state.started_at,
        "settings": {
            "trade_type": settings.trade_type,
            "strategy": settings.strategy,
            "base_order_size": settings.base_order_size,
            "open_spread": settings.open_spread,
            "close_spread": settings.close_spread,
        },
        "state": bot_state.data or {},
    })


# ============================================================
# SAVE SYMBOL SETTINGS
# ============================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def save_symbol_settings(request, symbol):
    symbol = symbol.upper()
    user = request.user

    try:
        with transaction.atomic():
            UserSymbolSettings.objects.update_or_create(
                user=user,
                symbol=symbol,
                defaults=request.data
            )

        return Response({"success": True})

    except Exception as e:
        logger.error(f"Save settings failed: {e}")
        return Response({"error": str(e)}, status=400)


# ============================================================
# START BOT
# ============================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_bot(request, symbol):
    symbol = symbol.upper()
    user = request.user

    try:
        BotState.objects.update_or_create(
            user=user,
            symbol=symbol,
            defaults={
                "is_active": True,
                "started_at": timezone.now(),
                "last_update": timezone.now(),
                "data": {},
            }
        )

        trade_engine.start_background(symbol, user.id)

        return Response({"success": True})

    except Exception as e:
        logger.error(f"Bot start failed: {e}")
        return Response({"error": str(e)}, status=400)


# ============================================================
# STOP BOT
# ============================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def stop_bot(request, symbol):
    symbol = symbol.upper()
    user = request.user

    try:
        BotState.objects.filter(
            user=user,
            symbol=symbol
        ).update(
            is_active=False,
            last_update=timezone.now()
        )

        trade_engine.stop(symbol, user.id)

        return Response({"success": True})

    except Exception as e:
        logger.error(f"Bot stop failed: {e}")
        return Response({"error": str(e)}, status=400)


# ============================================================
# TRADES
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


# ============================================================
# LOGS
# ============================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_bot_logs(request):
    limit = int(request.query_params.get("limit", 50))

    logs = BotLog.objects.filter(
        user=request.user
    ).order_by("-created_at")[:limit]

    return Response({
        "logs": BotLogSerializer(logs, many=True).data
    })
