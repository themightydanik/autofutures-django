# ===== apps/trading/trade_engine.py =====
import asyncio
import datetime
import logging
import random

from django.utils import timezone
from channels.layers import get_channel_layer

from .models import BotState, UserSymbolSettings, BotLog

logger = logging.getLogger(__name__)


class TradeEngine:

    def __init__(self):
        self.running = {}        # user_id:symbol → bool
        self.tasks = {}          # user_id:symbol → asyncio.Task
        self.channel_layer = get_channel_layer()

        # Хранилище тиков для графика
        self.ticks = {}          # key: user_id:symbol → {"open":[], "close":[], "real":[]}

    # ======================================================
    # START BOT
    # ======================================================
    def start(self, symbol, user):
        symbol = symbol.upper()
        key = f"{user.id}:{symbol}"

        if self.running.get(key):
            logger.info(f"Bot already running for {key}")
            return

        self.running[key] = True
        loop = asyncio.get_event_loop()
        task = loop.create_task(self.main_loop(user, symbol))
        self.tasks[key] = task

        logger.info(f"Bot started: {key}")

    # ======================================================
    # STOP BOT
    # ======================================================
    def stop(self, symbol, user):
        symbol = symbol.upper()
        key = f"{user.id}:{symbol}"

        self.running[key] = False
        logger.info(f"Bot stop requested: {key}")

    # ======================================================
    # MAIN LOOP — обновление 1–2 раза/сек
    # ======================================================
    async def main_loop(self, user, symbol):
        symbol = symbol.upper()
        key = f"{user.id}:{symbol}"

        logger.info(f"Main loop started for {key}")

        while self.running.get(key, False):
            try:
                await self.update_state(user, symbol)
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Main loop error [{key}]: {e}")

        logger.info(f"Main loop finished for {key}")

    # ======================================================
    # UPDATE BOT STATE
    # ======================================================
    async def update_state(self, user, symbol):

        # -------- 1. Load user settings --------
        try:
            settings = UserSymbolSettings.objects.get(user=user, symbol=symbol)
        except UserSymbolSettings.DoesNotExist:
            return

        # -------- 2. Load or create BotState --------
        bot, _ = BotState.objects.update_or_create(
            user=user,
            symbol=symbol,
            defaults={"last_update": timezone.now()}
        )

        # ----------------------------------------------
        # 3. EMULATED MARKET DATA (заменим API бирж позже)
        # ----------------------------------------------
        bid1 = random.uniform(100, 101)
        ask1 = bid1 + random.uniform(0.01, 0.05)

        bid2 = random.uniform(100, 101)
        ask2 = bid2 + random.uniform(0.01, 0.05)

        open_spread = (bid2 - ask1) / ask1 * 100
        close_spread = (bid1 - ask2) / ask2 * 100

        # ----------------------------------------------
        # 4. TICKS (для графика)
        # ----------------------------------------------
        key = f"{user.id}:{symbol}"

        if key not in self.ticks:
            self.ticks[key] = {"open": [], "close": [], "real": []}

        ticks = self.ticks[key]

        ticks["open"].append(float(open_spread))
        ticks["close"].append(float(close_spread))

        # "real spread" — спред, по которому был бы вход
        real_spread = open_spread if settings.side == "LONG" else close_spread
        ticks["real"].append(float(real_spread))

        # ограничиваем длину массивов
        for arr in ticks.values():
            if len(arr) > 200:
                arr.pop(0)

        # ----------------------------------------------
        # 5. Update BotState.data
        # ----------------------------------------------
        bot.data = {
            "exchange_1": settings.exchange_1,
            "exchange_2": settings.exchange_2,
            "side": settings.side,
            "open_spread": round(open_spread, 5),
            "close_spread": round(close_spread, 5),

            "bid_1": bid1,
            "ask_1": ask1,
            "bid_2": bid2,
            "ask_2": ask2,

            "ticks": ticks,
            "timestamp": str(datetime.datetime.now()),

            # заглушка — позже добавим entry/exit
            "entry_spread": None,
            "orders": 0,
            "pnl": 0,
            "pnl_percent": 0,
        }

        bot.save()

        # ----------------------------------------------
        # 6. WS PUSH
        # ----------------------------------------------
        await self.push_update(user, symbol, bot.data)

    # ======================================================
    # WS PUSH
    # ======================================================
    async def push_update(self, user, symbol, data):
        """
        Отправляет обновление в группу trading_<user_id>
        """
        group = f"trading_{user.id}"

        await self.channel_layer.group_send(
            group,
            {
                "type": "trading.update",
                "symbol": symbol,
                "data": data,
            }
        )


trade_engine = TradeEngine()
