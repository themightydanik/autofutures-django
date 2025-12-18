# apps/exchanges/market_urls.py

from django.urls import path
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .exchange_service import exchange_service
import asyncio


def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ======================================================
# SYMBOL SEARCH (autocomplete for terminal)
# ======================================================
@api_view(["GET"])
def search_symbols(request):
    q = request.query_params.get("q", "").upper()

    if len(q) < 2:
        return Response([])

    try:
        results = run_async(
            exchange_service.search_symbols(
                query=q,
                exchanges=["binance", "bybit", "bitget", "gateio", "mexc", "bingx"],
                limit=20
            )
        )
        return Response(results)

    except Exception as e:
        return Response({"detail": str(e)}, status=500)


# ======================================================
# PRICE
# ======================================================
@api_view(['GET'])
def get_price(request, exchange_id, symbol):
    price = run_async(
        exchange_service.get_ticker_price(exchange_id, symbol)
    )
    return Response({
        "exchange": exchange_id,
        "symbol": symbol,
        "price": price
    })


# ======================================================
# PRICE HISTORY
# ======================================================
@api_view(['GET'])
def get_price_history(request, symbol):
    interval = request.query_params.get('interval', '1m')
    limit = int(request.query_params.get('limit', 100))

    history = run_async(
        exchange_service.get_price_history(symbol, interval, limit)
    )
    return Response(history)


# ======================================================
# TOP COINS
# ======================================================
@api_view(['GET'])
def get_top_coins(request):
    limit = int(request.query_params.get('limit', 10))
    coins = run_async(
        exchange_service.get_top_coins(limit)
    )
    return Response(coins)


urlpatterns = [
    path("search-symbols", search_symbols),
    path("price/<str:exchange_id>/<str:symbol>", get_price),
    path("price-history/<str:symbol>", get_price_history),
    path("top-coins", get_top_coins),
]
