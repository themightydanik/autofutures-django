# ===== apps/trading/consumers.py =====
from channels.generic.websocket import AsyncWebsocketConsumer
import json
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async
from .models import BotLog

User = get_user_model()

class TradingConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time trading updates"""
    
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.room_group_name = f'trading_{self.user_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial data
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'message': 'Connected to trading updates'
        }))
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        
        if data.get('type') == 'subscribe':
            # Send updates
            await self.send_updates()
    
    async def send_updates(self):
        """Send trading updates"""
        # TODO: Get real-time data
        await self.send(text_data=json.dumps({
            'type': 'update',
            'data': {
                'pnl': 0,
                'pnl_percent': 0,
                'active_trades': [],
                'latest_logs': [],
                'is_running': False
            }
        }))
    
    async def trading_update(self, event):
        """Receive message from room group"""
        await self.send(text_data=json.dumps(event['message']))
