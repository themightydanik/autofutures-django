# ===== apps/trading/trade_engine.py =====
import asyncio
import datetime
import logging
import random

from django.utils import timezone
from channels.layers import get_channel_layer

from .models import BotState, UserSymbolSettings, BotLog

logger = logging.getLogger(__name__)

# Пытаемся подключить ccxt
try:
    import ccxt
except ImportError:  # ccxt не установлен – работаем только на заглушках
    ccxt = None
    logger.warning("CCXT is not installed. TradeEngine will use emulated data only.")


# Маппинг наших id бирж → id в ccxt
CCXT_EXCHANGE_IDS = {
    "bybit": "bybit",
    "mexc": "mexc",      # при необходимости поменяешь на "mexc3"
    "gateio": "gateio",
    "bingx": "bingx",
    "bitget": "bitget",
}


class TradeEngine:

    def __init__(self):
        # user_id:symbol → bool
        self.running = {}
        # user_id:symbol → asyncio.Task
        self.tasks = {}
        # Хранилище тиков для графика
        self.ticks = {}   # key: "user_id:symbol" → {"open": [], "close": [], "real": []}

        # WebSocket
        self.channel_layer = get_channel_layer()

        # Кэш клиентов ccxt по биржам
        self.ccxt_clients = {}  # exchange_id → ccxt instance

    # ------------------------------------------------------
    # Вспомогательный ключ
    # ------------------------------------------------------
    def _key(self, user, symbol: str) -> str:
        return f"{user.id}:{symbol.upper()}"

    # ------------------------------------------------------
    # Получить / создать ccxt-клиента
    # ------------------------------------------------------
    def _get_ccxt_client(self, exchange_id: str):
        """
        exchange_id: 'bybit', 'mexc', 'gateio', 'bingx', 'bitget'
        """
        if ccxt is None:
            return None

        ccxt_id = CCXT_EXCHANGE_IDS.get(exchange_id)
        if not ccxt_id:
            logger.warning(f"Unsupported exchange_id for ccxt: {exchange_id}")
            return None

        if ccxt_id not in self.ccxt_clients:
            # Создаём инстанс с rateLimit
            cls = getattr(ccxt, ccxt_id, None)
            if not cls:
                logger.warning(f"CCXT class not found for: {ccxt_id}")
                return None

            self.ccxt_clients[ccxt_id] = cls({
                "enableRateLimit": True,
            })

        return self.ccxt_clients[ccxt_id]

    # ------------------------------------------------------
    # Запуск бота
    # ------------------------------------------------------
    def start(self, symbol, user):
        symbol = symbol.upper()
        key = self._key(user, symbol)

        if self.running.get(key):
            logger.info(f"Bot already running for {key}")
            return

        self.running[key] = True
        loop = asyncio.get_event_loop()
        task = loop.create_task(self.main_loop(user, symbol))
        self.tasks[key] = task

        logger.info(f"Bot started: {key}")

    # ------------------------------------------------------
    # Остановка бота
    # ------------------------------------------------------
    def stop(self, symbol, user):
        symbol = symbol.upper()
        key = self._key(user, symbol)

        self.running[key] = False
        logger.info(f"Bot stop requested: {key}")

    # ------------------------------------------------------
    # Основной цикл – 1 апдейт в секунду
    # ------------------------------------------------------
    async def main_loop(self, user, symbol):
        symbol = symbol.upper()
        key = self._key(user, symbol)

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

    # ------------------------------------------------------
    # Запуск синхронной функции в отдельном потоке
    # ------------------------------------------------------
    async def _run_sync(self, func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    # ------------------------------------------------------
    # Конструируем фьючерсный символ (упрощённо)
    # ------------------------------------------------------
    def _make_futures_symbol(self, base_symbol: str) -> str:
        """
        Очень упрощённо: BTC → BTC/USDT:USDT
        При необходимости можешь переопределить маппинг для каждой биржи.
        """
        base_symbol = base_symbol.upper()
        return f"{base_symbol}/USDT:USDT"

    # ------------------------------------------------------
    # Снимок рынка по бирже через ccxt
    # ------------------------------------------------------
    async def _fetch_market_snapshot(self, exchange_id: str, symbol: str):
        """
        Возвращает dict:
        {
          "bid": float,
          "ask": float,
          "funding_rate": float | None,
          "next_funding_time": str | None,
          "mark_price": float | None,
          "max_size": float | None,
        }
        или None, если не удалось получить.
        """
        client = self._get_ccxt_client(exchange_id)
        if client is None:
            return None

        market_symbol = self._make_futures_symbol(symbol)

        try:
            # Ticker
            ticker = await self._run_sync(client.fetch_ticker, market_symbol)
        except Exception as e:
            logger.warning(f"[{exchange_id}] fetch_ticker failed for {market_symbol}: {e}")
            return None

        # Основные поля
        bid = ticker.get("bid") or ticker.get("bidPrice")
        ask = ticker.get("ask") or ticker.get("askPrice")
        last = ticker.get("last") or ticker.get("lastPrice")

        # Funding
        funding_rate = None
        next_funding = None
        try:
            if hasattr(client, "fetch_funding_rate"):
                funding = await self._run_sync(client.fetch_funding_rate, market_symbol)
                funding_rate = funding.get("fundingRate")
                # Пробуем взять время следующего фандинга
                ts = funding.get("fundingTimestamp") or funding.get("nextFundingTimestamp")
                if ts:
                    next_funding = datetime.datetime.fromtimestamp(
                        ts / 1000.0
                    ).isoformat()
        except Exception as e:
            logger.debug(f"[{exchange_id}] fetch_funding_rate failed: {e}")

        # Лимиты размера (максимальный размер ордера)
        max_size = None
        try:
            markets = await self._run_sync(client.load_markets)
            market = markets.get(market_symbol)
            if market:
                limits = market.get("limits") or {}
                amount_limits = limits.get("amount") or {}
                max_size = amount_limits.get("max")
        except Exception as e:
            logger.debug(f"[{exchange_id}] load_markets/limits failed: {e}")

        return {
            "bid": float(bid) if bid is not None else None,
            "ask": float(ask) if ask is not None else None,
            "funding_rate": float(funding_rate) if funding_rate is not None else None,
            "next_funding_time": next_funding,
            "mark_price": float(last) if last is not None else None,
            "max_size": float(max_size) if max_size is not None else None,
        }

    # ------------------------------------------------------
    # Обновление состояния бота
    # ------------------------------------------------------
    async def update_state(self, user, symbol):
        symbol = symbol.upper()

        # 1. Настройки пользователя
        try:
            settings = UserSymbolSettings.objects.get(user=user, symbol=symbol)
        except UserSymbolSettings.DoesNotExist:
            return

        exchange_1 = settings.exchange_1
        exchange_2 = settings.exchange_2

        # 2. Обновляем / создаём BotState
        bot, _ = BotState.objects.update_or_create(
            user=user,
            symbol=symbol,
            defaults={"last_update": timezone.now()}
        )

        # ----------------------------------------------
        # 3. Снимаем данные с бирж (если ccxt доступен)
        # ----------------------------------------------
        snap1 = await self._fetch_market_snapshot(exchange_1, symbol) if exchange_1 else None
        snap2 = await self._fetch_market_snapshot(exchange_2, symbol) if exchange_2 else None

        # Если не получилось получить с реальных бирж — фолбэк на рандом как раньше
        if not snap1 or not snap2 or snap1["bid"] is None or snap2["bid"] is None:
            bid1 = random.uniform(100, 101)
            ask1 = bid1 + random.uniform(0.01, 0.05)

            bid2 = random.uniform(100, 101)
            ask2 = bid2 + random.uniform(0.01, 0.05)

            funding_1 = None
            funding_2 = None
            next_funding_1 = None
            next_funding_2 = None
            mark_1 = bid1
            mark_2 = bid2
            max_size_1 = None
            max_size_2 = None
        else:
            bid1 = snap1["bid"]
            ask1 = snap1["ask"]
            bid2 = snap2["bid"]
            ask2 = snap2["ask"]

            funding_1 = snap1["funding_rate"]
            funding_2 = snap2["funding_rate"]
            next_funding_1 = snap1["next_funding_time"]
            next_funding_2 = snap2["next_funding_time"]
            mark_1 = snap1["mark_price"]
            mark_2 = snap2["mark_price"]
            max_size_1 = snap1["max_size"]
            max_size_2 = snap2["max_size"]

        # ----------------------------------------------
        # 4. Расчёт спредов
        # ----------------------------------------------
        # как и раньше:
        #   open_spread  ≈ вход по ask1 / bid2
        #   close_spread ≈ выход по bid1 / ask2
        open_spread = (bid2 - ask1) / ask1 * 100 if ask1 and bid2 else 0
        close_spread = (bid1 - ask2) / ask2 * 100 if bid1 and ask2 else 0

        key = self._key(user, symbol)
        if key not in self.ticks:
            self.ticks[key] = {"open": [], "close": [], "real": []}

        ticks = self.ticks[key]
        ticks["open"].append(float(open_spread))
        ticks["close"].append(float(close_spread))

        # "real_spread" – условный спред, по которому открылись бы позиции
        real_spread = open_spread if settings.side == "LONG" else close_spread
        ticks["real"].append(float(real_spread))

        # ограничиваем до 200 точек
        for arr in ticks.values():
            if len(arr) > 200:
                arr.pop(0)

        # ----------------------------------------------
        # 5. Заполняем bot.data
        # ----------------------------------------------
        bot.data = {
            "exchange_1": exchange_1,
            "exchange_2": exchange_2,
            "side": settings.side,

            # Спреды
            "open_spread": round(open_spread, 5),
            "close_spread": round(close_spread, 5),

            # Биржа 1
            "funding_rate_1": funding_1,
            "next_funding_1": next_funding_1,
            "bid_1": bid1,
            "ask_1": ask1,
            "mark_price_1": mark_1,
            "max_size_1": max_size_1,

            # Биржа 2
            "funding_rate_2": funding_2,
            "next_funding_2": next_funding_2,
            "bid_2": bid2,
            "ask_2": ask2,
            "mark_price_2": mark_2,
            "max_size_2": max_size_2,

            # Ticks для графика
            "ticks": ticks,
            "timestamp": datetime.datetime.now().isoformat(),

            # Пока заглушки — позже добавим реальную торговлю
            "entry_spread": None,
            "orders": 0,
            "pnl": 0,
            "pnl_percent": 0,
            "realized_pnl": 0,
        }

        bot.save()

        # ----------------------------------------------
        # 6. Отправляем обновление в WebSocket
        # ----------------------------------------------
        await self.push_update(user, symbol, bot.data)

    # ------------------------------------------------------
    # WS PUSH
    # ------------------------------------------------------
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


# Синглтон
trade_engine = TradeEngine()
