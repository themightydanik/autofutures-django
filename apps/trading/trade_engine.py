# ===== apps/trading/trade_engine.py =====
import asyncio
import datetime
import logging
import json

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from django.utils import timezone

from .models import BotState, UserSymbolSettings, BotLog

logger = logging.getLogger(__name__)


class TradeEngine:

    def __init__(self):
        # Рабочие процессы для каждого юзера/символа
        self.active_tasks = {}   # key: f"{user_id}:{symbol}"
        self.running = {}        # key: f"{user_id}:{symbol}" → bool

        # Websocket channel layer
        self.channel_layer = get_channel_layer()

    # ======================================================
    # Запустить бота
    # ======================================================
    def start(self, symbol: str, user):
        key = f"{user.id}:{symbol}"

        # Уже запущен?
        if key in self.running and self.running[key]:
            logger.info(f"Bot already running for {key}")
            return

        self.running[key] = True

        # Создаём таск
        loop = asyncio.get_event_loop()
        task = loop.create_task(self.main_loop(symbol, user))
        self.active_tasks[key] = task

        logger.info(f"Bot started for {key}")

    # ======================================================
    # Остановить бота
    # ======================================================
    def stop(self, symbol: str, user):
        key = f"{user.id}:{symbol}"
        self.running[key] = False

        logger.info(f"Stop requested for bot {key}")

    # ======================================================
    # Основной цикл бота
    # ======================================================
    async def main_loop(self, symbol: str, user):
        key = f"{user.id}:{symbol}"
        logger.info(f"Main loop started for {key}")

        while self.running.get(key, False):

            try:
                await self.update_bot_state(symbol, user)
                await asyncio.sleep(1.0)  # обновление раз в секунду
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Bot loop error for {key}: {e}")

        logger.info(f"Bot main loop finished for {key}")

    # ======================================================
    # Обновление данных — вызывается каждую секунду
    # ======================================================
    async def update_bot_state(self, symbol, user):

        # 1. Получаем настройки пользователя
        try:
            settings = UserSymbolSettings.objects.get(user=user, symbol=symbol)
        except UserSymbolSettings.DoesNotExist:
            logger.warning(f"No settings for user {user.id}, symbol {symbol}")
            return

        # 2. Получаем или создаём состояние бота
        bot, _ = BotState.objects.update_or_create(
            user=user,
            symbol=symbol,
            defaults={"last_update": timezone.now()}
        )

        # 3. Эмуляция реальных биржевых данных
        # позже тут будет вызов exchange_service
        import random
        bid1 = random.uniform(0.5, 2.0)
        ask1 = bid1 + random.uniform(0.01, 0.03)

        bid2 = random.uniform(0.5, 2.0)
        ask2 = bid2 + random.uniform(0.01, 0.03)

        open_spread = (bid2 - ask1) / ask1 * 100
        close_spread = (bid1 - ask2) / ask2 * 100

        # 4. Обновляем состояние бота
        bot.data = {
            "exchange_1": settings.exchange_1,
            "exchange_2": settings.exchange_2,
            "side": settings.side,
            "open_spread": float(open_spread),
            "close_spread": float(close_spread),
            "timestamp": str(datetime.datetime.now()),
            "bid_1": bid1,
            "ask_1": ask1,
            "bid_2": bid2,
            "ask_2": ask2,
        }
        bot.save()

        # 5. Отправляем обновление фронтенду
        await self.push_ws_update(user, symbol, bot.data)

    # ======================================================
    # WebSocket push
    # ======================================================
    async def push_ws_update(self, user, symbol, data):
        group = f"user_{user.id}"

        await self.channel_layer.group_send(
            group,
            {
                "type": "bot.update",
                "symbol": symbol,
                "data": data,
            }
        )

    # ======================================================
    # Вспомогательная: Websocket handler
    # ======================================================
    @staticmethod
    def format_ws_message(event):
        return {
            "symbol": event.get("symbol"),
            "data": event.get("data"),
        }


# Синглтон
trade_engine = TradeEngine()
