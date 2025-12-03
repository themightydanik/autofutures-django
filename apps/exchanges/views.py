# apps/exchanges/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from django.utils import timezone

from .models import ExchangeConnection
from .serializers import ExchangeConnectionSerializer, BalanceSerializer, ExchangeInfoSerializer
from .exchange_service import exchange_service
from .encryption import encryption_service


# ============================================================
# 1. Supported Exchanges (static list)
# ============================================================

SUPPORTED = [
    {"id": "binance", "name": "Binance", "tier": 1, "has_spot": True, "has_futures": True, "maker_fee": 0.0002, "taker_fee": 0.0004},
    {"id": "bybit",   "name": "Bybit",   "tier": 1, "has_spot": True, "has_futures": True, "maker_fee": 0.0002, "taker_fee": 0.00055},
    {"id": "bitget",  "name": "Bitget",  "tier": 1, "has_spot": True, "has_futures": True, "maker_fee": 0.0002, "taker_fee": 0.0005},
    {"id": "gateio",  "name": "Gate.io", "tier": 2, "has_spot": True, "has_futures": True, "maker_fee": 0.00015, "taker_fee": 0.00035},
    {"id": "mexc",    "name": "MEXC",    "tier": 2, "has_spot": True, "has_futures": True, "maker_fee": 0.0002, "taker_fee": 0.0005},
    {"id": "bingx",   "name": "BingX",   "tier": 2, "has_spot": True, "has_futures": True, "maker_fee": 0.0002, "taker_fee": 0.0005},
]


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_supported_exchanges(request):
    return Response(SUPPORTED)
    

# ============================================================
# 2. Connect Exchange
# ============================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def connect_exchange(request):
    serializer = ExchangeConnectionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    data = serializer.validated_data
    user = request.user
    exchange_id = data["exchange_id"]

    # Encrypt keys
    api_key_encrypted = encryption_service.encrypt(data["api_key"])
    secret_key_encrypted = encryption_service.encrypt(data["secret_key"])
    passphrase = data.get("passphrase") or ""
    passphrase_encrypted = encryption_service.encrypt(passphrase) if passphrase else None

    # Save to DB
    ExchangeConnection.objects.update_or_create(
        user=user,
        exchange_id=exchange_id,
        defaults={
            "api_key_encrypted": api_key_encrypted,
            "secret_key_encrypted": secret_key_encrypted,
            "passphrase_encrypted": passphrase_encrypted,
            "is_active": True,
            "last_sync": timezone.now(),
        },
    )

    # Test connection via ccxt
    try:
        ex = exchange_service._get_client(user.id, exchange_id)
        if ex:
            exchange_service.connections[user.id][exchange_id] = ex

    except Exception as e:
        return Response({"success": False, "error": str(e)}, status=400)

    return Response({"success": True})


# ============================================================
# 3. Disconnect Exchange
# ============================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def disconnect_exchange(request, exchange_id):
    user = request.user

    ExchangeConnection.objects.filter(
        user=user,
        exchange_id=exchange_id,
    ).update(is_active=False)

    # Remove from cache
    key = f"{user.id}:{exchange_id}"
    if key in exchange_service.connections.get(user.id, {}):
        del exchange_service.connections[user.id][exchange_id]

    return Response({"success": True})


# ============================================================
# 4. Manage (LIST CONNECTED)
# ============================================================

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def manage_exchanges(request):
    user = request.user

    conns = ExchangeConnection.objects.filter(user=user, is_active=True)

    formatted = [
        {"exchange_id": c.exchange_id, "id": c.exchange_id, "connected": True}
        for c in conns
    ]

    return Response({"exchanges": formatted})


# ============================================================
# 5. Get Balance (USDT)
# ============================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_balance(request, exchange_id):
    try:
        data = asyncio.run(exchange_service.get_balance(request.user.id, exchange_id))
        return Response(data)
    except Exception as e:
        return Response({"error": str(e)}, status=400)
