# ===== apps/exchanges/exchange_service.py =====
import ccxt
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, List

from .encryption import encryption_service
from .models import ExchangeConnection

logger = logging.getLogger(__name__)


# ================================================================
# МАППИНГ БИРЖ ДЛЯ ФЬЮЧЕРСОВ
# ================================================================
EXCHANGE_CCXT_MAP = {
    "bybit": "bybit",
    "binance": "binanceusdm",   # обязательно futures USDM
    "bitget": "bitget",
    "gateio": "gate",
    "mexc": "mexc",
    "bingx": "bingx",
}


# ================================================================
# Exchange Service (универсальный клиент CCXT)
# ================================================================
class ExchangeService:

    def __init__(self):
        # user_id → {exchange_id → ccxt_instance}
        self.connections = {}

    # ------------------------------------------------------------
    # Получить или создать CCXT клиента
    # ------------------------------------------------------------
    def _get_client(self, user_id: int, exchange_id: str):
        """
        Возвращает готовый CCXT клиент с подключенными API-ключами.
        Если соединения нет — создаёт автоматически.
        """
        exchange_id = exchange_id.lower()

        if exchange_id not in EXCHANGE_CCXT_MAP:
            raise ValueError(f"Unsupported exchange: {exchange_id}")

        if user_id not in self.connections:
            self.connections[user_id] = {}

        # Уже создан?
        if exchange_id in self.connections[user_id]:
            return self.connections[user_id][exchange_id]

        # Получаем ключи из БД
        conn: Optional[ExchangeConnection] = (
            ExchangeConnection.objects
            .filter(user_id=user_id, exchange_id=exchange_id, is_active=True)
            .first()
        )

        if not conn:
            raise ValueError(f"No API keys stored for {exchange_id}")

        api_key = encryption_service.decrypt(conn.api_key_encrypted)
        secret_key = encryption_service.decrypt(conn.secret_key_encrypted)
        passphrase = encryption_service.decrypt(conn.passphrase_encrypted) if conn.passphrase_encrypted else None

        ccxt_id = EXCHANGE_CCXT_MAP[exchange_id]

        if not hasattr(ccxt, ccxt_id):
            raise ValueError(f"CCXT does not support class {ccxt_id}")

        # Создаём клиента
        client_class = getattr(ccxt, ccxt_id)
        client = client_class({
            "apiKey": api_key,
            "secret": secret_key,
            "password": passphrase,
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",       # работаем только с фьючами
            }
        })

        # Сохраняем
        self.connections[user_id][exchange_id] = client

        return client

    # ------------------------------------------------------------
    # Загружаем markets (один раз)
    # ------------------------------------------------------------
    async def load_markets(self, user_id: int, exchange_id: str):
        client = self._get_client(user_id, exchange_id)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: client.load_markets())

    # ------------------------------------------------------------
    # Получить позицию по фьючерсам (BTCUSDT)
    # ------------------------------------------------------------
    async def get_position(self, user_id: int, exchange_id: str, symbol: str):
        client = self._get_client(user_id, exchange_id)
        sym = f"{symbol}/USDT"

        loop = asyncio.get_event_loop()
        try:
            positions = await loop.run_in_executor(None, lambda: client.fetch_positions([sym]))
            if positions and len(positions) > 0:
                return positions[0]
            return None
        except Exception as e:
            logger.warning(f"Position fetch failed {exchange_id}: {e}")
            return None

    # ------------------------------------------------------------
    # Создать ордер (market)
    # ------------------------------------------------------------
    async def create_order(self, user_id: int, exchange_id: str, symbol: str, side: str, amount: float):
        """
        side: "buy" или "sell"
        """
        client = self._get_client(user_id, exchange_id)
        market_symbol = f"{symbol}/USDT"

        loop = asyncio.get_event_loop()
        try:
            order = await loop.run_in_executor(
                None,
                lambda: client.create_order(market_symbol, "market", side, amount)
            )
            return order
        except Exception as e:
            logger.error(f"Order failed [{exchange_id} {side} {symbol}]: {e}")
            raise

    # ------------------------------------------------------------
    # Закрыть позицию
    # ------------------------------------------------------------
    async def close_position(self, user_id: int, exchange_id: str, symbol: str, amount: float, long_or_short: str):
        client = self._get_client(user_id, exchange_id)
        market_symbol = f"{symbol}/USDT"

        side = "sell" if long_or_short == "long" else "buy"

        loop = asyncio.get_event_loop()
        try:
            order = await loop.run_in_executor(
                None,
                lambda: client.create_order(market_symbol, "market", side, amount)
            )
            return order
        except Exception as e:
            logger.error(f"Close position failed {exchange_id}: {e}")
            raise

    # ------------------------------------------------------------
    # Получить текущие цены (bid, ask, mark)
    # ------------------------------------------------------------
    async def get_markets_snapshot(self, user_id: int, exchange_id: str, symbol: str) -> Optional[Dict]:
        client = self._get_client(user_id, exchange_id)
        market_symbol = f"{symbol}/USDT"

        loop = asyncio.get_event_loop()

        try:
            ticker = await loop.run_in_executor(None, lambda: client.fetch_ticker(market_symbol))
        except Exception as e:
            logger.warning(f"[{exchange_id}] fetch_ticker failed: {e}")
            return None

        bid = ticker.get("bid") or ticker.get("bidPrice")
        ask = ticker.get("ask") or ticker.get("askPrice")
        last = ticker.get("last") or ticker.get("lastPrice")

        # funding rate
        funding = None
        next_funding = None
        if hasattr(client, "fetch_funding_rate"):
            try:
                f = await loop.run_in_executor(None, lambda: client.fetch_funding_rate(market_symbol))
                funding = f.get("fundingRate")
                ts = f.get("fundingTimestamp") or f.get("nextFundingTimestamp")
                if ts:
                    next_funding = datetime.fromtimestamp(ts / 1000).isoformat()
            except Exception:
                pass

        return {
            "bid": float(bid) if bid else None,
            "ask": float(ask) if ask else None,
            "mark_price": float(last) if last else None,
            "funding_rate": float(funding) if funding else None,
            "next_funding_time": next_funding,
        }

    # ------------------------------------------------------------
    # Установить кредитное плечо
    # ------------------------------------------------------------
    async def set_leverage(self, user_id: int, exchange_id: str, symbol: str, leverage: int):
        client = self._get_client(user_id, exchange_id)
        market_symbol = f"{symbol}/USDT"

        if not hasattr(client, "set_leverage"):
            return False

        loop = asyncio.get_event_loop()

        try:
            await loop.run_in_executor(None, lambda: client.set_leverage(leverage, market_symbol))
            return True
        except Exception as e:
            logger.warning(f"set_leverage failed for {exchange_id}: {e}")
            return False

    # ------------------------------------------------------------
    # Баланс USDT
    # ------------------------------------------------------------
    async def get_balance(self, user_id: int, exchange_id: str):
        client = self._get_client(user_id, exchange_id)
        loop = asyncio.get_event_loop()

        try:
            balance = await loop.run_in_executor(None, client.fetch_balance)
            usdt = balance.get("USDT", {})
            return {
                "exchange": exchange_id,
                "currency": "USDT",
                "free": float(usdt.get("free", 0)),
                "locked": float(usdt.get("used", 0)),
                "total": float(usdt.get("total", 0)),
            }
        except Exception as e:
            logger.error(f"Balance failed {exchange_id}: {e}")
            return {"exchange": exchange_id, "currency": "USDT", "free": 0, "locked": 0, "total": 0}


# Singleton instance
exchange_service = ExchangeService()
