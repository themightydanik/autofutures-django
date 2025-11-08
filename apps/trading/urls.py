# ===== apps/trading/urls.py =====
from django.urls import path
from . import views

urlpatterns = [
    path('start', views.start_trading, name='start_trading'),
    path('stop', views.stop_trading, name='stop_trading'),
    path('status', views.get_trade_status, name='trade_status'),
    path('active', views.get_active_trades, name='active_trades'),
    path('history', views.get_trade_history, name='trade_history'),
    path('logs', views.get_bot_logs, name='bot_logs'),
]
