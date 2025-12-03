# apps/trading/routing.py

from django.urls import re_path
from .consumers import TradingConsumer

websocket_urlpatterns = [
    re_path(r"ws/(?P<user_id>[^/]+)$", TradingConsumer.as_asgi()),
]
