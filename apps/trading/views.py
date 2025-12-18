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
    try:
        symbol = symbol.upper()
        user = request.user

        settings, _ = UserSymbolSettings.objects.get_or_create(
            user=user,
            symbol=symbol,
            defaults={
                "exchange_1": "bybit",
                "exchange_2": "gateio",
                "side": "LONG",
                "open_spread": 0.2,
                "close_spread": 0.05,
                "order_size": 0.0,
                "order_size_usdt": 10.0,
                "max_orders": 1,
                "open_ticks": 0,
                "close_ticks": 0,
                "force_stop": False,
                "total_stop": False,
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
                "side": settings.side,
                "exchange_1": settings.exchange_1,
                "exchange_2": settings.exchange_2,
                "open_spread": settings.open_spread,
                "close_spread": settings.close_spread,
                "order_size": settings.order_size,
                "order_size_usdt": settings.order_size_usdt,
                "max_orders": settings.max_orders,
                "open_ticks": settings.open_ticks,
                "close_ticks": settings.close_ticks,
                "force_stop": settings.force_stop,
                "total_stop": settings.total_stop,
            },
            "state": bot_state.data or {},
        })

    except Exception as e:
        logger.exception("get_symbol_state failed")
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


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
            settings, _ = UserSymbolSettings.objects.get_or_create(
                user=user,
                symbol=symbol
            )

            allowed_fields = {
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
            }

            for field, value in request.data.items():
                if field in allowed_fields:
                    setattr(settings, field, value)

            settings.save()

        return Response({"success": True})

    except Exception as e:
        logger.exception("Save settings failed")
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
        logger.exception("Bot start failed")
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

        trade_engine.stop_background(symbol, user.id)

        return Response({"success": True})

    except Exception as e:
        logger.exception("Bot stop failed")
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
        user=request.user
    ).order_by("-opened_at")[:limit]

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
