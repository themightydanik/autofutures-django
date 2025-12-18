from django.urls import re_path
from .consumers import TradingConsumer

websocket_urlpatterns = [
    re_path(r"^ws/$", TradingConsumer.as_asgi()),
]
