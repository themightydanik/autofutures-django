# ===== apps/trading/trade_engine.py =====
import asyncio
import datetime
import logging
import random

from django.utils import timezone
from channels.layers import get_channel_layer

from .models import BotState, UserSymbolSettings, BotLog, Trade

logger = logging.getLogger(__name__)


class TradeEngine:

    def __init__(self):
        self.running = {}
        self.tasks = {}
        self.channel_layer = get_channel_layer()

        # ticks for chart
        self.ticks = {}

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
    # MAIN LOOP
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
    # UPDATE BOT STATE (with real trading logic)
    # ======================================================
    async def update_state(self, user, symbol):
        # ---- 1. LOAD SETTINGS ----
        try:
            s = UserSymbolSettings.objects.get(user=user, symbol=symbol)
        except UserSymbolSettings.DoesNotExist:
            return

        # ---- 2. LOAD BOT STATE ----
        bot, _ = BotState.objects.update_or_create(
            user=user, symbol=symbol,
            defaults={"last_update": timezone.now()}
        )

        # ---- 3. EMULATED MARKET DATA ----
        bid1 = random.uniform(100, 101)
        ask1 = bid1 + random.uniform(0.01, 0.05)

        bid2 = random.uniform(100, 101)
        ask2 = bid2 + random.uniform(0.01, 0.05)

        open_spread = (bid2 - ask1) / ask1 * 100
        close_spread = (bid1 - ask2) / ask2 * 100

        # ---- 4. Prepare ticks ----
        key = f"{user.id}:{symbol}"
        if key not in self.ticks:
            self.ticks[key] = {"open": [], "close": [], "real": []}

        ticks = self.ticks[key]
        ticks["open"].append(float(open_spread))
        ticks["close"].append(float(close_spread))
        real_spread = open_spread if s.side == "LONG" else close_spread
        ticks["real"].append(float(real_spread))

        for arr in ticks.values():
            if len(arr) > 200:
                arr.pop(0)

        # ---- 5. TRADING LOGIC ----
        entry = bot.data.get("entry_spread")
        orders = bot.data.get("orders", 0)
        order_size = s.order_size
        max_orders = s.max_orders

        pnl = 0
        pnl_pct = 0

        # ===== ENTRY CONDITIONS =====
        if entry is None and orders < max_orders:
            if s.side == "LONG" and open_spread >= s.open_spread:
                # enter long-spread
                bot.data["entry_spread"] = float(open_spread)
                bot.data["entry_price_1"] = ask1
                bot.data["entry_price_2"] = bid2
                bot.data["orders"] = orders + 1

                BotLog.objects.create(
                    user=user,
                    symbol=symbol,
                    log_type="ENTRY",
                    message=f"LONG spread entered at {open_spread:.4f}%"
                )

            elif s.side == "SHORT" and close_spread <= s.close_spread:
                bot.data["entry_spread"] = float(close_spread)
                bot.data["entry_price_1"] = bid1
                bot.data["entry_price_2"] = ask2
                bot.data["orders"] = orders + 1

                BotLog.objects.create(
                    user=user,
                    symbol=symbol,
                    log_type="ENTRY",
                    message=f"SHORT spread entered at {close_spread:.4f}%"
                )

        # ===== EXIT CONDITIONS =====
        entry = bot.data.get("entry_spread")
        if entry is not None:
            if s.side == "LONG":
                # we exit when close_spread falls
                if close_spread <= s.close_spread:
                    pnl = entry - close_spread
                    pnl_pct = (pnl / abs(entry)) * 100 if entry != 0 else 0

                    BotLog.objects.create(
                        user=user,
                        symbol=symbol,
                        log_type="EXIT",
                        message=f"LONG exited. PnL: {pnl:.4f}%"
                    )

                    # clear position
                    bot.data["entry_spread"] = None

            elif s.side == "SHORT":
                # exit when open_spread grows
                if open_spread >= s.open_spread:
                    pnl = close_spread - entry
                    pnl_pct = (pnl / abs(entry)) * 100 if entry != 0 else 0

                    BotLog.objects.create(
                        user=user,
                        symbol=symbol,
                        log_type="EXIT",
                        message=f"SHORT exited. PnL: {pnl:.4f}%"
                    )

                    bot.data["entry_spread"] = None

        # ---- 6. Update BotState.data ----
        bot.data.update({
            "exchange_1": s.exchange_1,
            "exchange_2": s.exchange_2,
            "side": s.side,

            "open_spread": round(open_spread, 5),
            "close_spread": round(close_spread, 5),

            "bid_1": bid1,
            "ask_1": ask1,
            "bid_2": bid2,
            "ask_2": ask2,

            "ticks": ticks,
            "timestamp": str(datetime.datetime.now()),

            "pnl": pnl,
            "pnl_percent": pnl_pct,
        })

        bot.save()

        # ---- 7. PUSH WS UPDATE ----
        await self.push_update(user, symbol, bot.data)

    # ======================================================
    # WS PUSH
    # ======================================================
    async def push_update(self, user, symbol, data):
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
