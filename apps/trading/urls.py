# apps/trading/urls.py

from django.urls import path
from . import views

urlpatterns = [

    # === USER SYMBOL SETTINGS ===
    path('settings/<str:symbol>', views.get_symbol_settings, name='get_symbol_settings'),
    path('settings/<str:symbol>/save', views.save_symbol_settings, name='save_symbol_settings'),

    # === BOT CONTROL ===
    path('start/<str:symbol>', views.start_bot, name='start_bot'),
    path('stop/<str:symbol>', views.stop_bot, name='stop_bot'),
    path('state/<str:symbol>', views.get_bot_state, name='get_bot_state'),

    # === TRADES & LOGS ===
    path('active', views.get_active_trades, name='active_trades'),
    path('history', views.get_trade_history, name='trade_history'),
    path('logs', views.get_bot_logs, name='bot_logs'),
]
