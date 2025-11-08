import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autofutures.settings')

# Инициализируем Django ASGI приложение до импорта Channels
django_asgi_app = get_asgi_application()

# Теперь импортируем Channels
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Попробуем импортировать routing, если есть ошибка - используем пустой список
try:
    from apps.trading.routing import websocket_urlpatterns
except ImportError:
    websocket_urlpatterns = []

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
