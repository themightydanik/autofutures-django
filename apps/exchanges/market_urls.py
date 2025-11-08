# ===== apps/exchanges/market_urls.py =====
from django.urls import path
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .exchange_service import exchange_service
import asyncio

@api_view(['GET'])
def get_price(request, exchange_id, symbol):
    """Get current price"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        price = loop.run_until_complete(exchange_service.get_ticker_price(exchange_id, symbol))
        return Response({'exchange': exchange_id, 'symbol': symbol, 'price': price})
    except Exception as e:
        return Response({'detail': str(e)}, status=400)

@api_view(['GET'])
def get_price_history(request, symbol):
    """Get price history"""
    interval = request.query_params.get('interval', '1m')
    limit = int(request.query_params.get('limit', 100))
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        history = loop.run_until_complete(exchange_service.get_price_history(symbol, interval, limit))
        return Response(history)
    except Exception as e:
        return Response({'detail': str(e)}, status=400)

@api_view(['GET'])
def get_top_coins(request):
    """Get top coins by volume"""
    limit = int(request.query_params.get('limit', 10))
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        coins = loop.run_until_complete(exchange_service.get_top_coins(limit))
        return Response(coins)
    except Exception as e:
        return Response({'detail': str(e)}, status=400)

urlpatterns = [
    path('price/<str:exchange_id>/<str:symbol>', get_price),
    path('price-history/<str:symbol>', get_price_history),
    path('top-coins', get_top_coins),
]
