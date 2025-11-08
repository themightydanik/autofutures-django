# ===== apps/arbitrage/urls.py =====
from django.urls import path
from . import views

urlpatterns = [
    path('analyze', views.analyze_arbitrage, name='analyze_arbitrage'),
    path('scan', views.scan_arbitrage, name='scan_arbitrage'),
]
