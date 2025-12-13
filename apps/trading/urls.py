from django.urls import path
from . import views

urlpatterns = [

    # === MAIN DASHBOARD STATE ===
    path('<str:symbol>', views.get_symbol_state, name='get_symbol_state'),

    # === SAVE SETTINGS ===
    path('<str:symbol>/settings', views.save_symbol_settings, name='save_symbol_settings'),

    # === BOT CONTROL ===
    path('<str:symbol>/start', views.start_bot, name='start_bot'),
    path('<str:symbol>/stop', views.stop_bot, name='stop_bot'),

    # === TRADES & LOGS ===
    path('active', views.get_active_trades, name='active_trades'),
    path('history', views.get_trade_history, name='trade_history'),
    path('logs', views.get_bot_logs, name='bot_logs'),
]
