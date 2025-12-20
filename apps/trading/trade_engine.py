# ===== apps/trading/trade_engine.py =====
import asyncio
import datetime
import logging
import random
from decimal import Decimal

from django.utils import timezone
from channels.layers import get_channel_layer

from .models import BotState, UserSymbolSettings, BotLog, Trade
from apps.exchanges.models import ExchangeConnection
from apps.exchanges.encryption import encryption_service

logger = logging.getLogger(__name__)

# Пытаемся подключить ccxt
try:
    import ccxt
except ImportError:
    ccxt = None
    logger.warning("CCXT is not installed. TradeEngine will use emulated data only.")

# Маппинг наших id бирж → id в ccxt
CCXT_EXCHANGE_IDS = {
    "bybit": "bybit",
    "binance": "binanceusdm",
    "mexc": "mexc",      # возможно "mexc3" – при необходимости поменяешь
    "gateio": "gate",
    "bingx": "bingx",
    "bitget": "bitget",
}

# Оценочные комиссии (в долях, не в %), если не удалось получить fee из ордера
# (примерно 0.06% TAKER)
DEFAULT_FEE_RATE = 0.0006


class TradeEngine:
    """
    Реальный фьючерсный спред-арбитраж:
    - exchange_1 / exchange_2
    - side = LONG / SHORT (для первой биржи)
    - open_spread / close_spread (в %)
    - order_size (в монетах)
    - max_orders (количество одновременных спредов)
    """

    def __init__(self):
        # user_id:symbol → bool
        self.running = {}
        # user_id:symbol → asyncio.Task
        self.tasks = {}
        # Хранилище тиков для графика: key → {"open": [], "close": [], "real": []}
        self.ticks = {}

        # WebSocket
        self.channel_layer = get_channel_layer()

        # Кэш ccxt-клиентов по пользователю и бирже
        # key: f"{user_id}:{exchange_id}" → ccxt instance
        self.ccxt_clients = {}

        # =====================================================
        # Dedicated background asyncio loop (REQUIRED for Django)
        # =====================================================
        import threading

        self.loop = asyncio.new_event_loop()

        def _run_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        self.loop_thread = threading.Thread(
            target=_run_loop,
            args=(self.loop,),
            daemon=True,
        )
        self.loop_thread.start()


    # ------------------------------------------------------
    # Вспомогательный ключ
    # ------------------------------------------------------
    def _key(self, user, symbol: str) -> str:
        return f"{user.id}:{symbol.upper()}"

    # ------------------------------------------------------
    # Получить / создать ccxt-клиента с ключами пользователя
    # ------------------------------------------------------
    def _get_ccxt_client(self, user, exchange_id: str):
        """
        Возвращает аутентифицированный ccxt-клиент фьючерсов.
        Если нет ключей — возвращает None.
        """
        if ccxt is None:
            return None

        ccxt_id = CCXT_EXCHANGE_IDS.get(exchange_id)
        if not ccxt_id:
            logger.warning(f"Unsupported exchange_id for ccxt: {exchange_id}")
            return None

        cache_key = f"{user.id}:{exchange_id}"
        if cache_key in self.ccxt_clients:
            return self.ccxt_clients[cache_key]

        # Ищем подключение с API ключами
        try:
            conn = ExchangeConnection.objects.get(
                user=user, exchange_id=exchange_id, is_active=True
            )
        except ExchangeConnection.DoesNotExist:
            logger.warning(
                f"No active ExchangeConnection for user={user.id}, exchange={exchange_id}"
            )
            return None

        api_key = encryption_service.decrypt(conn.api_key_encrypted)
        secret = encryption_service.decrypt(conn.secret_key_encrypted)
        passphrase = (
            encryption_service.decrypt(conn.passphrase_encrypted)
            if conn.passphrase_encrypted
            else None
        )

        cls = getattr(ccxt, ccxt_id, None)
        if not cls:
            logger.warning(f"CCXT class not found for: {ccxt_id}")
            return None

        params = {
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
        }

        # Для некоторых бирж нужен password/passphrase
        if passphrase:
            params["password"] = passphrase

        # Фьючерсы / swap (USDT-m)
        params.setdefault("options", {})
        params["options"].setdefault("defaultType", "swap")

        client = cls(params)
        self.ccxt_clients[cache_key] = client
        return client

    # ------------------------------------------------------
    # Асинхронный wrapper для sync-методов ccxt
    # ------------------------------------------------------
    async def _run_sync(self, func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    # ------------------------------------------------------
    # Построение unified futures-символа
    # ------------------------------------------------------
    def _make_futures_symbol(self, base_symbol: str) -> str:
        """
        По умолчанию: BTC → BTC/USDT:USDT (унифицированный ccxt-символ
        для USDT-маржинальных perpetual swap).
        При необходимости потом сделаем маппинг по биржам.
        """
        base_symbol = base_symbol.upper()
        return f"{base_symbol}/USDT:USDT"

    # ------------------------------------------------------
    # Снимок рынка по бирже через ccxt
    # ------------------------------------------------------
    async def _fetch_market_snapshot(self, user, exchange_id: str, symbol: str):
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
        if ccxt is None:
            return None

        ccxt_id = CCXT_EXCHANGE_IDS.get(exchange_id)
        if not ccxt_id:
            return None

        # Сначала пытаемся использовать аутентифицированный клиент
        client = self._get_ccxt_client(user, exchange_id)

        # Если нет ключей — создаём публичный клиент
        if client is None:
            cls = getattr(ccxt, ccxt_id, None)
            if not cls:
                return None
            client = cls({"enableRateLimit": True})

        market_symbol = self._make_futures_symbol(symbol)

        # --- Ticker ---
        try:
            ticker = await self._run_sync(client.fetch_ticker, market_symbol)
        except Exception as e:
            logger.warning(f"[{exchange_id}] fetch_ticker failed for {market_symbol}: {e}")
            return None

        bid = ticker.get("bid") or ticker.get("bidPrice")
        ask = ticker.get("ask") or ticker.get("askPrice")
        last = ticker.get("last") or ticker.get("lastPrice")

        # --- Funding ---
        funding_rate = None
        next_funding = None
        try:
            if hasattr(client, "fetch_funding_rate"):
                funding = await self._run_sync(client.fetch_funding_rate, market_symbol)
                funding_rate = funding.get("fundingRate")
                ts = funding.get("fundingTimestamp") or funding.get("nextFundingTimestamp")
                if ts:
                    next_funding = datetime.datetime.fromtimestamp(
                        ts / 1000.0
                    ).isoformat()
        except Exception as e:
            logger.debug(f"[{exchange_id}] fetch_funding_rate failed: {e}")

        # --- Лимиты размера ---
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
    # Создать один фьючерсный ордер (одна нога)
    # ------------------------------------------------------
    async def _open_leg(self, user, exchange_id: str, symbol: str, direction: str, amount: float):
        """
        direction: 'long' или 'short'
        Возвращает dict:
        {
          "price": float,
          "amount": float,
          "fee": float,
        }
        или None при ошибке.
        """
        client = self._get_ccxt_client(user, exchange_id)
        if client is None:
            logger.warning(
                f"Cannot open leg – no trading client for user={user.id}, exchange={exchange_id}"
            )
            return None

        market_symbol = self._make_futures_symbol(symbol)

        # LONG → buy, SHORT → sell
        if direction.lower() == "long":
            side = "buy"
        else:
            side = "sell"

        try:
            order = await self._run_sync(
                client.create_order,
                market_symbol,
                "market",
                side,
                amount,
            )
        except Exception as e:
            logger.error(
                f"create_order failed user={user.id}, ex={exchange_id}, sym={market_symbol}: {e}"
            )
            return None

        # Пытаемся достать среднюю цену
        price = (
            order.get("average")
            or order.get("price")
            or (order.get("info") or {}).get("avgPrice")
        )

        # Пытаемся достать комиссию
        fee_total = 0.0
        if order.get("fee"):
            fee_total += float(order["fee"].get("cost", 0) or 0)
        if order.get("fees"):
            fee_total += sum(float(f.get("cost", 0) or 0) for f in order["fees"])

        # Фолбэк — приблизительная комиссия
        if fee_total == 0 and price:
            fee_total = float(price) * float(amount) * DEFAULT_FEE_RATE

        if not price:
            # Фолбэк: берём last price при отсутствии
            try:
                ticker = await self._run_sync(client.fetch_ticker, market_symbol)
                price = ticker.get("last") or ticker.get("close")
            except Exception:
                price = None

        return {
            "price": float(price) if price is not None else None,
            "amount": float(amount),
            "fee": float(fee_total),
        }

    # ------------------------------------------------------
    # Закрыть ногу (противоположным ордером)
    # ------------------------------------------------------
    async def _close_leg(self, user, exchange_id: str, symbol: str, direction: str, amount: float):
        """
        direction: 'long' или 'short' (НАПРАВЛЕНИЕ ИСХОДНОЙ ПОЗИЦИИ)
        Для закрытия мы делаем reverse:
        - если была long → sell
        - если была short → buy
        """
        client = self._get_ccxt_client(user, exchange_id)
        if client is None:
            logger.warning(
                f"Cannot close leg – no trading client for user={user.id}, exchange={exchange_id}"
            )
            return None

        market_symbol = self._make_futures_symbol(symbol)

        # reverse side
        if direction.lower() == "long":
            side = "sell"
        else:
            side = "buy"

        try:
            order = await self._run_sync(
                client.create_order,
                market_symbol,
                "market",
                side,
                amount,
            )
        except Exception as e:
            logger.error(
                f"close_order failed user={user.id}, ex={exchange_id}, sym={market_symbol}: {e}"
            )
            return None

        price = (
            order.get("average")
            or order.get("price")
            or (order.get("info") or {}).get("avgPrice")
        )

        fee_total = 0.0
        if order.get("fee"):
            fee_total += float(order["fee"].get("cost", 0) or 0)
        if order.get("fees"):
            fee_total += sum(float(f.get("cost", 0) or 0) for f in order["fees"])

        if fee_total == 0 and price:
            fee_total = float(price) * float(amount) * DEFAULT_FEE_RATE

        if not price:
            try:
                ticker = await self._run_sync(client.fetch_ticker, market_symbol)
                price = ticker.get("last") or ticker.get("close")
            except Exception:
                price = None

        return {
            "price": float(price) if price is not None else None,
            "amount": float(amount),
            "fee": float(fee_total),
        }

    # ------------------------------------------------------
    # Открыть арбитражную позицию (две ноги)
    # ------------------------------------------------------
    async def _open_arbitrage_position(
        self,
        user,
        symbol: str,
        settings,
        bid1: float,
        ask1: float,
        bid2: float,
        ask2: float,
        open_spread: float,
    ):
        """
        Открываем:
        - exchange_1: side (LONG/SHORT)
        - exchange_2: противоположная сторона
        """
        exchange_1 = settings.exchange_1
        exchange_2 = settings.exchange_2
        base_side = settings.side.upper()  # LONG / SHORT
        amount = float(settings.order_size or 0.0)

        if amount <= 0:
            logger.warning(f"order_size=0, skip open_arbitrage for user={user.id}, {symbol}")
            return

        # Определяем направление для каждой биржи
        if base_side == "LONG":
            leg1_dir = "long"
            leg2_dir = "short"
        else:
            leg1_dir = "short"
            leg2_dir = "long"

        # --- Открываем ногу 1 ---
        leg1 = await self._open_leg(user, exchange_1, symbol, leg1_dir, amount)
        if not leg1 or leg1["price"] is None:
            logger.error("Failed to open leg1, aborting arbitrage open")
            return

        # --- Открываем ногу 2 ---
        leg2 = await self._open_leg(user, exchange_2, symbol, leg2_dir, amount)
        if not leg2 or leg2["price"] is None:
            logger.error("Failed to open leg2, arbitrage HALF-OPEN (требуется ручной контроль)")
            # TODO: в идеале попытаться компенсировать и закрыть leg1
            return

        entry_price_1 = leg1["price"]
        entry_price_2 = leg2["price"]
        total_fee = float(leg1["fee"] + leg2["fee"])

        # Создаём запись Trade
        notional = (entry_price_1 + entry_price_2) * amount
        entry_spread = open_spread  # в %

        trade = Trade.objects.create(
            user=user,
            trade_type="arbitrage",
            symbol=symbol,
            side=base_side.lower(),  # long/short
            entry_price=Decimal(str((entry_price_1 + entry_price_2) / 2.0)),
            amount=Decimal(str(amount)),
            pnl=Decimal("0"),
            pnl_percent=Decimal("0"),
            fees=Decimal(str(total_fee)),
            status="active",
            exchanges={
                "exchange_1": {
                    "id": exchange_1,
                    "direction": leg1_dir,   # long/short
                    "entry_price": entry_price_1,
                    "amount": amount,
                    "fee_open": leg1["fee"],
                },
                "exchange_2": {
                    "id": exchange_2,
                    "direction": leg2_dir,
                    "entry_price": entry_price_2,
                    "amount": amount,
                    "fee_open": leg2["fee"],
                },
                "entry_spread": entry_spread,
                "notional": notional,
            },
            strategy="futures_spread",
        )

        # Лог
        BotLog.objects.create(
            user=user,
            trade=trade,
            log_type="buy",
            message=(
                f"Opened arbitrage {symbol}: "
                f"{exchange_1} {leg1_dir.upper()} @ {entry_price_1}, "
                f"{exchange_2} {leg2_dir.upper()} @ {entry_price_2}, "
                f"entry_spread={entry_spread:.4f}%"
            ),
            details=trade.exchanges,
        )

    # ------------------------------------------------------
    # Закрыть ВСЕ активные арбитражные позиции для символа
    # ------------------------------------------------------
    async def _close_all_arbitrage_positions(
        self,
        user,
        symbol: str,
        settings,
        bid1: float,
        ask1: float,
        bid2: float,
        ask2: float,
        close_spread: float,
    ):
        exchange_1 = settings.exchange_1
        exchange_2 = settings.exchange_2

        active_trades = Trade.objects.filter(
            user=user,
            symbol=symbol,
            trade_type="arbitrage",
            status="active",
        )

        if not active_trades.exists():
            return

        for trade in active_trades:
            ex_data = trade.exchanges or {}
            leg1_info = ex_data.get("exchange_1") or {}
            leg2_info = ex_data.get("exchange_2") or {}

            leg1_dir = leg1_info.get("direction", "long")
            leg2_dir = leg2_info.get("direction", "short")
            amount = float(leg1_info.get("amount") or trade.amount or 0.0)

            if amount <= 0:
                continue

            # Закрываем ноги
            leg1_close = await self._close_leg(user, exchange_1, symbol, leg1_dir, amount)
            leg2_close = await self._close_leg(user, exchange_2, symbol, leg2_dir, amount)

            if not leg1_close or not leg2_close or leg1_close["price"] is None or leg2_close["price"] is None:
                logger.error(
                    f"Failed to close arbitrage trade {trade.id} fully, legs: {leg1_close}, {leg2_close}"
                )
                continue

            exit_price_1 = leg1_close["price"]
            exit_price_2 = leg2_close["price"]

            close_fee_total = float(leg1_close["fee"] + leg2_close["fee"])
            total_fee = float(trade.fees) + close_fee_total

            entry_price_1 = float(leg1_info.get("entry_price") or trade.entry_price)
            entry_price_2 = float(leg2_info.get("entry_price") or trade.entry_price)
            entry_spread = float(ex_data.get("entry_spread") or 0.0)

            amount_f = float(amount)
            notional = float(ex_data.get("notional") or (entry_price_1 + entry_price_2) * amount_f)

            # PnL по ногам
            # Если base_side == LONG → leg1 long, leg2 short
            # Если base_side == SHORT → leg1 short, leg2 long
            base_side = trade.side.upper()

            if base_side == "LONG":
                # leg1 long: profit = (exit - entry) * amount
                profit1 = (exit_price_1 - entry_price_1) * amount_f
                # leg2 short: profit = (entry - exit) * amount
                profit2 = (entry_price_2 - exit_price_2) * amount_f
            else:
                # leg1 short
                profit1 = (entry_price_1 - exit_price_1) * amount_f
                # leg2 long
                profit2 = (exit_price_2 - entry_price_2) * amount_f

            pnl_total = profit1 + profit2 - total_fee
            pnl_percent = (pnl_total / notional * 100.0) if notional > 0 else 0.0

            # Обновляем Trade
            trade.exit_price = Decimal(str((exit_price_1 + exit_price_2) / 2.0))
            trade.fees = Decimal(str(total_fee))
            trade.pnl = Decimal(str(pnl_total))
            trade.pnl_percent = Decimal(str(pnl_percent))
            trade.status = "completed"
            trade.closed_at = timezone.now()

            ex_data["exit_spread"] = close_spread
            ex_data["exit_price_1"] = exit_price_1
            ex_data["exit_price_2"] = exit_price_2
            ex_data["fee_close"] = close_fee_total
            trade.exchanges = ex_data

            trade.save()

            BotLog.objects.create(
                user=user,
                trade=trade,
                log_type="profit" if pnl_total >= 0 else "error",
                message=(
                    f"Closed arbitrage {symbol}, PnL={pnl_total:.4f} USDT "
                    f"({pnl_percent:.42f}%), close_spread={close_spread:.4f}%"
                ),
                details=ex_data,
            )

    # ------------------------------------------------------
    # async START/STOP (под твой views.py)
    # ------------------------------------------------------
    async def start(self, symbol, user):
        symbol = symbol.upper()
        key = self._key(user, symbol)

        if self.running.get(key):
            logger.info(f"Bot already running for {key}")
            return

        self.running[key] = True
        asyncio.create_task(self.main_loop(user, symbol))

        logger.info(f"Bot started: {key}")

    async def stop(self, symbol, user):
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
    # Обновление состояния бота (сердце логики)
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

        if not exchange_1 or not exchange_2:
            return

        # 2. BotState
        bot, _ = BotState.objects.update_or_create(
            user=user,
            symbol=symbol,
            defaults={"last_update": timezone.now()},
        )

        # 3. Снимаем данные с бирж
        snap1 = await self._fetch_market_snapshot(user, exchange_1, symbol)
        snap2 = await self._fetch_market_snapshot(user, exchange_2, symbol)

        # Если не получилось — fallback на рандом, без торговли
        if (
            not snap1
            or not snap2
            or snap1.get("bid") is None
            or snap2.get("bid") is None
            or snap1.get("ask") is None
            or snap2.get("ask") is None
        ):
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

            real_market = False
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

            real_market = True

        # 4. Расчёт спредов
        open_spread = (bid2 - ask1) / ask1 * 100 if ask1 and bid2 else 0
        close_spread = (bid1 - ask2) / ask2 * 100 if bid1 and ask2 else 0

        key = self._key(user, symbol)
        if key not in self.ticks:
            self.ticks[key] = {"open": [], "close": [], "real": []}

        ticks = self.ticks[key]
        ticks["open"].append(float(open_spread))
        ticks["close"].append(float(close_spread))

        # Реальный "спред позиции"
        base_side = settings.side.upper()  # LONG/SHORT
        real_spread = open_spread if base_side == "LONG" else close_spread
        ticks["real"].append(float(real_spread))

        # Ограничиваем до 200 точек
        for arr in ticks.values():
            if len(arr) > 200:
                arr.pop(0)

        # 5. Вход/выход из позиций (только если есть реальные данные и ключи)
        active_trades = Trade.objects.filter(
            user=user,
            symbol=symbol,
            trade_type="arbitrage",
            status="active",
        )

        # Условия блокировок
        force_stop = settings.force_stop
        total_stop = settings.total_stop

        # --- ВХОД ---
        if (
            real_market
            and not force_stop
            and not total_stop
            and active_trades.count() < (settings.max_orders or 1)
        ):
            # Если side=LONG → ждём, когда open_spread >= open_spread_threshold
            # Если side=SHORT → ждём обратного условия
            open_thr = float(settings.open_spread or 0.0)

            if base_side == "LONG":
                open_condition = open_spread >= open_thr
            else:
                open_condition = open_spread <= -open_thr if open_thr > 0 else open_spread <= open_thr

            if open_condition:
                await self._open_arbitrage_position(
                    user,
                    symbol,
                    settings,
                    bid1,
                    ask1,
                    bid2,
                    ask2,
                    open_spread,
                )
                # Перечитываем активные сделки
                active_trades = Trade.objects.filter(
                    user=user,
                    symbol=symbol,
                    trade_type="arbitrage",
                    status="active",
                )

        # --- ВЫХОД ---
        if real_market and active_trades.exists():
            close_thr = float(settings.close_spread or 0.0)

            # Для LONG, как правило, хотим, чтобы close_spread был <= порога
            # Для SHORT — зеркально.
            if base_side == "LONG":
                close_condition = close_spread <= close_thr
            else:
                close_condition = close_spread >= -close_thr if close_thr > 0 else close_spread >= close_thr

            if close_condition or force_stop or total_stop:
                await self._close_all_arbitrage_positions(
                    user,
                    symbol,
                    settings,
                    bid1,
                    ask1,
                    bid2,
                    ask2,
                    close_spread,
                )
                active_trades = Trade.objects.filter(
                    user=user,
                    symbol=symbol,
                    trade_type="arbitrage",
                    status="active",
                )

        # 6. Текущий нереализованный PnL по активным сделкам
        unrealized_pnl = 0.0
        unrealized_pnl_percent = 0.0

        if active_trades.exists():
            total_notional = 0.0
            for t in active_trades:
                ex_data = t.exchanges or {}
                entry_spread = float(ex_data.get("entry_spread") or 0.0)
                notional = float(ex_data.get("notional") or 0.0) or float(
                    t.entry_price * t.amount * 2
                )

                # Аппроксимация: PnL ≈ (entry_spread - current_spread) * notional / 100
                if base_side == "LONG":
                    spread_diff = entry_spread - close_spread
                else:
                    spread_diff = close_spread - entry_spread

                pnl_est = spread_diff / 100.0 * notional

                unrealized_pnl += pnl_est
                total_notional += notional

            if total_notional > 0:
                unrealized_pnl_percent = unrealized_pnl / total_notional * 100.0

        # 7. Обновляем bot.data
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

            # Статистика по ордерам
            "orders": active_trades.count(),
            "pnl": unrealized_pnl,
            "pnl_percent": unrealized_pnl_percent,
            "realized_pnl": 0,  # можно суммировать по closed trades, если нужно
        }

        bot.save()

        # 8. WS push
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

    # ------------------------------------------------------
    # SYNC wrappers (для вызова из Django views)
    # ------------------------------------------------------
    def start_background(self, symbol, user_id):
        from django.contrib.auth import get_user_model
        from asyncio import run_coroutine_threadsafe

        User = get_user_model()

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error(f"User not found: {user_id}")
            return

        run_coroutine_threadsafe(
            self.start(symbol, user),
            self.loop,
        )


    def stop_background(self, symbol, user_id):
        from django.contrib.auth import get_user_model
        from asyncio import run_coroutine_threadsafe

        User = get_user_model()

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error(f"User not found: {user_id}")
            return

        run_coroutine_threadsafe(
            self.stop(symbol, user),
            self.loop,
        )





# Синглтон
trade_engine = TradeEngine()
