import asyncio
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .exchange_service import exchange_service

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_symbols(request):
    """
    GET /api/market/search-symbols?q=ETH
    """
    query = request.query_params.get("q", "").strip()

    if not query:
        return Response([])

    # ❌ bitget исключаем (V1 API decommissioned)
    exchanges = ["binance", "bybit", "gateio", "mexc", "bingx"]

    try:
        # asyncio.run безопасен здесь (DRF sync view)
        results = asyncio.run(
            exchange_service.search_symbols(query, exchanges)
        )
        return Response(results)

    except Exception as e:
        logger.exception("Market symbol search failed")
        return Response([])
