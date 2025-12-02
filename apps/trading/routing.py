# ===== apps/trading/routing.py =====
from django.urls import re_path
from .consumers import TradingConsumer

websocket_urlpatterns = [
    re_path(r"ws/trading/(?P<user_id>[0-9a-f\-]+)/$", TradingConsumer.as_asgi()),
]
