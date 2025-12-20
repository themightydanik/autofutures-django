# apps/trading/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer


class TradingConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        # 🔥 FIX: Получаем user из scope (добавлен в middleware)
        user = self.scope.get("user")
        
        if not user or not user.is_authenticated:
            await self.close()
            return
        
        self.user_id = str(user.id)
        # 🔥 FIX: Используем правильное имя группы (как в trade_engine)
        self.group_name = f"trading_{self.user_id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "connection",
            "message": "WebSocket connected",
            "user_id": self.user_id
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        # Обрабатываем входящие сообщения от клиента
        try:
            data = json.loads(text_data)
            # На данный момент просто логируем
            print(f"Received from client: {data}")
        except Exception as e:
            print(f"Error parsing message: {e}")

    # 🔥 FIX: Добавляем обработчик для trading.update
    async def trading_update(self, event):
        """
        Обработчик для сообщений типа trading.update из trade_engine
        event = {
            "type": "trading.update",
            "symbol": "...",
            "data": {...}
        }
        """
        await self.send(text_data=json.dumps({
            "type": "bot.update",
            "symbol": event.get("symbol"),
            "data": event.get("data")
        }))
