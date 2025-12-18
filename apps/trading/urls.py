from django.urls import path
from . import views

urlpatterns = [
    path('<str:symbol>', views.get_symbol_state),
    path('<str:symbol>/settings', views.save_symbol_settings),
    path('<str:symbol>/start', views.start_bot),
    path('<str:symbol>/stop', views.stop_bot),

    path('active', views.get_active_trades),
    path('history', views.get_trade_history),
    path('logs', views.get_bot_logs),
]
