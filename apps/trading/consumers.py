# ===== apps/trading/consumers.py =====
from channels.generic.websocket import AsyncWebsocketConsumer
import json
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async

from .models import BotState, BotLog, UserSymbolSettings

User = get_user_model()


class TradingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer:
    - Один канал на пользователя
    - Получает real-time обновления из trade_engine
    - Может отдавать состояние по конкретному символу
    """

    async def connect(self):
        user_id = self.scope["url_route"]["kwargs"]["user_id"]

        # Проверяем что юзер существует
        self.user = await self.get_user(user_id)
        if not self.user:
            await self.close()
            return

        self.group_name = f"user_{self.user.id}"

        # Добавляем соединение в группу
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        # Отправляем приветственное сообщение
        await self.send_json({
            "type": "connection",
            "message": "WebSocket connected",
            "user_id": str(self.user.id)
        })

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # ======================================================
    # WebSocket receive — клиент подписывается на символ
    # ======================================================
    async def receive(self, text_data):
        data = json.loads(text_data)

        if data.get("type") == "subscribe":
            symbol = data.get("symbol")
            if not symbol:
                return

            # Выдаём состояние бота сразу
            bot_state = await self.get_bot_state(symbol)
            symbol_settings = await self.get_symbol_settings(symbol)

            await self.send_json({
                "type": "initial",
                "symbol": symbol,
                "bot_state": bot_state,
                "settings": symbol_settings,
            })

    # ======================================================
    # Посылается trade_engine через group_send(type="bot.update")
    # ======================================================
    async def bot_update(self, event):
        await self.send_json({
            "type": "update",
            "symbol": event.get("symbol"),
            "data": event.get("data"),
        })

    async def bot_log(self, event):
        await self.send_json({
            "type": "log",
            "data": event.get("data"),
        })

    async def bot_state(self, event):
        await self.send_json({
            "type": "state",
            "symbol": event.get("symbol"),
            "state": event.get("state"),
        })

    async def bot_error(self, event):
        await self.send_json({
            "type": "error",
            "message": event.get("message")
        })

    # ======================================================
    # DB operations async
    # ======================================================
    @database_sync_to_async
    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def get_bot_state(self, symbol):
        try:
            bot = BotState.objects.get(user=self.user, symbol=symbol)
            return {
                "is_running": bot.is_running,
                "started_at": bot.started_at,
                "data": bot.data,
            }
        except BotState.DoesNotExist:
            return None

    @database_sync_to_async
    def get_symbol_settings(self, symbol):
        try:
            s = UserSymbolSettings.objects.get(user=self.user, symbol=symbol)
            return {
                "exchange_1": s.exchange_1,
                "exchange_2": s.exchange_2,
                "side": s.side,
                "order_size": float(s.order_size),
                "close_spread": float(s.close_spread),
                "open_spread": float(s.open_spread),
                "max_orders": s.max_orders,
                "open_ticks": s.open_ticks,
                "close_ticks": s.close_ticks,
                "force_stop": s.force_stop,
                "total_stop": s.total_stop,
            }
        except UserSymbolSettings.DoesNotExist:
            return None

    async def send_json(self, data):
        await self.send(text_data=json.dumps(data))
