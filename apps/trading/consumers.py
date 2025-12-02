# ===== apps/trading/consumers.py =====
from channels.generic.websocket import AsyncWebsocketConsumer
import json
import logging

logger = logging.getLogger(__name__)


class TradingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time trading updates.
    Подписывается на trading_<user_id>.
    """

    async def connect(self):
        self.user_id = self.scope["url_route"]["kwargs"]["user_id"]

        # Группа для WS
        self.group_name = f"trading_{self.user_id}"

        # Присоединяемся к группе
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "connection",
            "message": f"Connected to trading channel {self.group_name}"
        }))

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        except Exception:
            pass

    async def receive(self, text_data):
        """
        Клиент может отправлять команды, если нужно
        например { "type": "subscribe" }
        """
        try:
            data = json.loads(text_data)
        except:
            return

        msg_type = data.get("type")

        if msg_type == "subscribe":
            await self.send(text_data=json.dumps({
                "type": "info",
                "message": "Subscribed"
            }))

    # ======================================================
    # HANDLER CALLED BY trade_engine.push_update()
    # ======================================================
    async def trading_update(self, event):
        """
        Принимает сообщения из channel_layer.group_send
        """
        await self.send(text_data=json.dumps({
            "type": "update",
            "symbol": event.get("symbol"),
            "data": event.get("data"),
        }))
