# ===== apps/exchanges/views.py =====

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.utils import timezone

from .models import ExchangeConnection
from .exchange_service import exchange_service
from .encryption import encryption_service


# ============================================================
# SUPPORTED EXCHANGES
# ============================================================

SUPPORTED = [
    {"id": "binance", "name": "Binance", "requires_passphrase": False},
    {"id": "bybit", "name": "Bybit", "requires_passphrase": False},
    {"id": "bitget", "name": "Bitget", "requires_passphrase": True},
    {"id": "gateio", "name": "Gate.io", "requires_passphrase": False},
    {"id": "mexc", "name": "MEXC", "requires_passphrase": False},
    {"id": "bingx", "name": "BingX", "requires_passphrase": False},
]


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_supported_exchanges(request):
    return Response({"exchanges": SUPPORTED})


# ============================================================
# LIST CONNECTED EXCHANGES (used by TradingContext & Settings)
# ============================================================

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def manage_exchanges(request):
    user = request.user

    conns = ExchangeConnection.objects.filter(user=user, is_active=True)

    connections = [
        {
            "exchange_id": c.exchange_id,
            "id": c.exchange_id,
            "connected": True,
            "connected_at": c.created_at,
        }
        for c in conns
    ]

    return Response({"connections": connections})


# ============================================================
# CONNECT EXCHANGE
# ============================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def connect_exchange(request):
    user = request.user

    exchange_id = request.data.get("exchange_id")
    api_key = request.data.get("api_key")
    secret_key = request.data.get("secret_key")
    passphrase = request.data.get("passphrase", "")

    if not exchange_id or not api_key or not secret_key:
        return Response(
            {"success": False, "error": "Missing credentials"},
            status=400,
        )

    ExchangeConnection.objects.update_or_create(
        user=user,
        exchange_id=exchange_id,
        defaults={
            "api_key_encrypted": encryption_service.encrypt(api_key),
            "secret_key_encrypted": encryption_service.encrypt(secret_key),
            "passphrase_encrypted": encryption_service.encrypt(passphrase)
            if passphrase
            else None,
            "is_active": True,
            "last_sync": timezone.now(),
        },
    )

    # Warm-up CCXT client (try to validate keys)
    try:
        exchange_service._get_private_client(user.id, exchange_id)
    except Exception as e:
        return Response({"success": False, "error": str(e)}, status=400)

    return Response({"success": True})


# ============================================================
# DISCONNECT EXCHANGE
# ============================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def disconnect_exchange(request):
    user = request.user
    exchange_id = request.data.get("exchange_id")

    if not exchange_id:
        return Response({"error": "exchange_id required"}, status=400)

    ExchangeConnection.objects.filter(
        user=user, exchange_id=exchange_id
    ).update(is_active=False)

    # Clear cached client
    if user.id in exchange_service.private_connections:
        exchange_service.private_connections[user.id].pop(exchange_id, None)

    return Response({"success": True})


# ============================================================
# ALL BALANCES (used by TradingContext)
# ============================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_all_balances(request):
    user = request.user
    result = {}

    conns = ExchangeConnection.objects.filter(user=user, is_active=True)

    for conn in conns:
        try:
            bal = exchange_service.get_balance_sync(user.id, conn.exchange_id)
            result[conn.exchange_id] = bal
        except Exception as e:
            result[conn.exchange_id] = {"error": str(e)}

    return Response(result)
