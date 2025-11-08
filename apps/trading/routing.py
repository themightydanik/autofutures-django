# ===== apps/trading/routing.py =====
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/(?P<user_id>[^/]+)$', consumers.TradingConsumer.as_asgi()),
]
