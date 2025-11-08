# ===== apps/exchanges/urls.py =====
from django.urls import path
from . import views

urlpatterns = [
    path('connect', views.connect_exchange, name='connect_exchange'),
    path('balances', views.get_balances, name='get_balances'),
    path('available-coins', views.get_available_coins, name='available_coins'),
    path('supported', views.get_supported_exchanges, name='supported_exchanges'),
]
