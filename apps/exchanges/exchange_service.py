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
    # bitget временно убираем (V1 API deprecated)
}


class ExchangeService:
    def __init__(self):
        self.private_connections = {}
        self.public_clients = {}

    # ============================================================
    # PUBLIC CLIENT (market data)
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
                "defaultType": "swap",  # 🔥 ВАЖНО: perpetual futures
            }
        })

        self.public_clients[exchange_id] = client
        return client

    # ============================================================
    # PRIVATE CLIENT (trading)
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
                "defaultType": "swap",  # 🔥 тоже swap
            }
        })

        self.private_connections[user_id][exchange_id] = client
        return client

# ============================================================
# SYMBOL SEARCH (FINAL, SAFE, USDT-SWAP ONLY)
# ============================================================
async def search_symbols(self, query: str, exchanges: List[str], limit: int = 20):
    query = query.upper().strip()
    results = {}

    for ex_id in exchanges:
        if ex_id not in EXCHANGE_CCXT_MAP:
            continue

        try:
            client = self._get_public_client(ex_id)

            markets = await asyncio.get_event_loop().run_in_executor(
                None, client.load_markets
            )

            for market in markets.values():

                # ✅ only perpetual swaps
                if not market.get("swap"):
                    continue

                # ✅ only USDT quoted
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
# PRICE (SAFE)
# ============================================================
async def get_ticker_price(self, exchange_id: str, symbol: str):

    # 🔒 safety: only BASE symbols allowed
    if "/" in symbol or symbol.endswith("BTC"):
        raise ValueError(f"Invalid symbol: {symbol}")

    client = self._get_public_client(exchange_id)
    market_symbol = f"{symbol}/USDT"

    ticker = await asyncio.get_event_loop().run_in_executor(
        None, lambda: client.fetch_ticker(market_symbol)
    )

    return ticker.get("last")


    # ============================================================
    # PRICE HISTORY
    # ============================================================
    async def get_price_history(self, symbol: str, interval="1m", limit=100):
        client = self._get_public_client("binance")
        market_symbol = f"{symbol}/USDT"

        ohlcv = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.fetch_ohlcv(
                market_symbol,
                timeframe=interval,
                limit=limit
            )
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
    # TOP COINS
    # ============================================================
    async def get_top_coins(self, limit=10):
        client = self._get_public_client("binance")

        tickers = await asyncio.get_event_loop().run_in_executor(
            None, client.fetch_tickers
        )

        usdt_pairs = [
            (symbol, data.get("quoteVolume", 0))
            for symbol, data in tickers.items()
            if data.get("swap") and symbol.endswith("USDT")
        ]

        usdt_pairs.sort(key=lambda x: x[1], reverse=True)

        return [
            {"symbol": s.replace("USDT", ""), "volume": v}
            for s, v in usdt_pairs[:limit]
        ]

    # ============================================================
    # BALANCE (SYNC WRAPPER)
    # ============================================================
    def get_balance_sync(self, user_id, exchange_id):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.get_balance(user_id, exchange_id)
            )
        finally:
            loop.close()

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
