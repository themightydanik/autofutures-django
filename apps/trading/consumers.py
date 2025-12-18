# apps/trading/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer


class TradingConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user_id = self.scope["url_route"]["kwargs"]["user_id"]
        self.group_name = f"user_{self.user_id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "connection",
           "message": "WebSocket connected"
       }))

  #   async def connect(self):
 #    print("🔥 WS CONNECT CALLED", self.scope)
  #   await self.accept()


    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # frontend sends: { "type": "subscribe", "user_id": "..." }
        data = json.loads(text_data)
        # No actions needed for now.

    async def bot_update(self, event):
        """
        event = {
            "type": "bot.update",
            "symbol": "...",
            "data": {...}
        }
        """
        await self.send(text_data=json.dumps(event))
