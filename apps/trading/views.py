# ===== apps/trading/views.py =====
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Trade, BotLog
from .serializers import TradeSerializer, BotLogSerializer, TradeParamsSerializer
from .trade_engine import trade_engine
from apps.users.models import UserSettings
import asyncio
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_trading(request):
    """Start trading bot"""
    serializer = TradeParamsSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        settings = UserSettings.objects.get(user=request.user)
        settings_dict = {
            'trade_type': settings.trade_type,
            'strategy': settings.strategy
        }
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            trade_engine.start_trading(request.user, settings_dict, serializer.validated_data)
        )
        
        return Response({'success': True, 'status': 'started'})
    except Exception as e:
        logger.error(f"Error starting trading: {str(e)}")
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_trading(request):
    """Stop trading bot"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(trade_engine.stop_trading(request.user))
        
        return Response({'success': True, 'status': 'stopped'})
    except Exception as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_trade_status(request):
    """Get trading status"""
    status_data = trade_engine.get_status(str(request.user.id))
    return Response(status_data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_trades(request):
    """Get active trades"""
    trades = Trade.objects.filter(user=request.user, status='active')
    serializer = TradeSerializer(trades, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_trade_history(request):
    """Get trade history"""
    limit = int(request.query_params.get('limit', 100))
    trades = Trade.objects.filter(user=request.user, status='completed')[:limit]
    serializer = TradeSerializer(trades, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_bot_logs(request):
    """Get bot activity logs"""
    limit = int(request.query_params.get('limit', 50))
    logs = BotLog.objects.filter(user=request.user)[:limit]
    serializer = BotLogSerializer(logs, many=True)
    return Response({'logs': serializer.data})
