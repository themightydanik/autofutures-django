import ccxt
import asyncio
import logging
from typing import List

from .encryption import encryption_service
from .models import ExchangeConnection

logger = logging.getLogger(__name__)

# ================================================================
# EXCHANGE MAP
# ================================================================
EXCHANGE_CCXT_MAP = {
    "binance": "binanceusdm",   # USDT-margined perpetuals
    "bybit": "bybit",
    "gateio": "gate",
    "mexc": "mexc",
    "bingx": "bingx",
}


class ExchangeService:
    def __init__(self):
        self.private_connections = {}
        self.public_clients = {}

    # ============================================================
    # PUBLIC CLIENT
    # ============================================================
    def _get_public_client(self, exchange_id: str):
        exchange_id = exchange_id.lower()

        if exchange_id not in EXCHANGE_CCXT_MAP:
            raise ValueError(f"Unsupported exchange: {exchange_id}")

        if exchange_id in self.public_clients:
            return self.public_clients[exchange_id]

        ccxt_id = EXCHANGE_CCXT_MAP[exchange_id]
        client_class = getattr(ccxt, ccxt_id)

        client = client_class({
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap",
            }
        })

        self.public_clients[exchange_id] = client
        return client

    # ============================================================
    # PRIVATE CLIENT
    # ============================================================
    def _get_private_client(self, user_id: int, exchange_id: str):
        exchange_id = exchange_id.lower()

        if exchange_id not in EXCHANGE_CCXT_MAP:
            raise ValueError(f"Unsupported exchange: {exchange_id}")

        if user_id not in self.private_connections:
            self.private_connections[user_id] = {}

        if exchange_id in self.private_connections[user_id]:
            return self.private_connections[user_id][exchange_id]

        conn = ExchangeConnection.objects.filter(
            user_id=user_id,
            exchange_id=exchange_id,
            is_active=True
        ).first()

        if not conn:
            raise ValueError(f"No API keys stored for {exchange_id}")

        api_key = encryption_service.decrypt(conn.api_key_encrypted)
        secret_key = encryption_service.decrypt(conn.secret_key_encrypted)
        passphrase = (
            encryption_service.decrypt(conn.passphrase_encrypted)
            if conn.passphrase_encrypted else None
        )

        ccxt_id = EXCHANGE_CCXT_MAP[exchange_id]
        client_class = getattr(ccxt, ccxt_id)

        client = client_class({
            "apiKey": api_key,
            "secret": secret_key,
            "password": passphrase,
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap",
            }
        })

        self.private_connections[user_id][exchange_id] = client
        return client

    # ============================================================
    # SYMBOL SEARCH (WORKING)
    # ============================================================
    async def search_symbols(self, query: str, exchanges: List[str], limit: int = 20):
        query = query.upper().strip()
        results = {}

        for ex_id in exchanges:
            try:
                client = self._get_public_client(ex_id)

                markets = await asyncio.get_event_loop().run_in_executor(
                    None, client.load_markets
                )

                for market in markets.values():

                    if not market.get("swap"):
                        continue

                    if market.get("quote") != "USDT":
                        continue

                    base = market.get("base")
                    if not base:
                        continue

                    if query not in base:
                        continue

                    if base not in results:
                        results[base] = {
                            "symbol": base,
                            "available_on": []
                        }

                    if ex_id not in results[base]["available_on"]:
                        results[base]["available_on"].append(ex_id)

                    if len(results) >= limit:
                        break

            except Exception as e:
                logger.warning(f"Symbol search failed {ex_id}: {e}")

        return list(results.values())[:limit]

    # ============================================================
    # PRICE
    # ============================================================
    async def get_ticker_price(self, exchange_id: str, symbol: str):
        client = self._get_public_client(exchange_id)
        market_symbol = f"{symbol}/USDT"

        try:
            ticker = await asyncio.get_event_loop().run_in_executor(
                None, lambda: client.fetch_ticker(market_symbol)
            )
            return ticker.get("last")
        except Exception as e:
            logger.warning(f"Price fetch failed {exchange_id} {symbol}: {e}")
            return None

    # ============================================================
    # PRICE HISTORY
    # ============================================================
    async def get_price_history(self, symbol: str, interval="1m", limit=100):
        client = self._get_public_client("binance")
        market_symbol = f"{symbol}/USDT"

        ohlcv = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.fetch_ohlcv(market_symbol, timeframe=interval, limit=limit)
        )

        return [
            {
                "time": c[0],
                "open": c[1],
                "high": c[2],
                "low": c[3],
                "close": c[4],
                "volume": c[5],
            }
            for c in ohlcv
        ]

    # ============================================================
    # BALANCE
    # ============================================================
    async def get_balance(self, user_id, exchange_id):
        client = self._get_private_client(user_id, exchange_id)

        balance = await asyncio.get_event_loop().run_in_executor(
            None, client.fetch_balance
        )

        usdt = balance.get("USDT", {})
        return {
            "exchange": exchange_id,
            "currency": "USDT",
            "free": float(usdt.get("free", 0)),
            "locked": float(usdt.get("used", 0)),
            "total": float(usdt.get("total", 0)),
        }


# ============================================================
# SINGLETON
# ============================================================
exchange_service = ExchangeService()
