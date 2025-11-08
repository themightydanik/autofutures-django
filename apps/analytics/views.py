# ===== apps/analytics/views.py =====
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Count, Avg, Max, Min
from apps.trading.models import Trade
from datetime import datetime, timedelta

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pnl_data(request):
    """Get PnL data for chart"""
    period = request.query_params.get('period', '24h')
    
    # Generate fake data for now
    pnl_chart = []
    for i in range(24):
        pnl_chart.append({
            'timestamp': (datetime.now() - timedelta(hours=23-i)).isoformat(),
            'time': f"{i}:00",
            'pnl': 0,
            'pnl_percent': 0
        })
    
    return Response({
        'chart_data': pnl_chart,
        'total_pnl': 0,
        'pnl_percent': 0
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_statistics(request):
    """Get trading statistics"""
    trades = Trade.objects.filter(user=request.user, status='completed')
    
    if not trades.exists():
        return Response({
            'total_trades': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'best_trade': 0,
            'worst_trade': 0,
            'trades_today': 0,
            'pnl_today': 0
        })
    
    successful = trades.filter(pnl__gt=0)
    failed = trades.filter(pnl__lt=0)
    
    today = datetime.now().date()
    trades_today = trades.filter(closed_at__date=today)
    
    return Response({
        'total_trades': trades.count(),
        'successful_trades': successful.count(),
        'failed_trades': failed.count(),
        'win_rate': (successful.count() / trades.count() * 100) if trades.count() > 0 else 0,
        'total_pnl': float(trades.aggregate(Sum('pnl'))['pnl__sum'] or 0),
        'best_trade': float(trades.aggregate(Max('pnl'))['pnl__max'] or 0),
        'worst_trade': float(trades.aggregate(Min('pnl'))['pnl__min'] or 0),
        'trades_today': trades_today.count(),
        'pnl_today': float(trades_today.aggregate(Sum('pnl'))['pnl__sum'] or 0)
    })
