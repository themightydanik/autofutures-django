# ===== apps/exchanges/exchange_service.py =====
import ccxt
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import logging
from .encryption import encryption_service

logger = logging.getLogger(__name__)

class ExchangeService:
    """Service for working with crypto exchanges"""
    
    SUPPORTED_EXCHANGES = {
        'binance': ccxt.binance,
        'gateio': ccxt.gateio,
        'bybit': ccxt.bybit,
    }
    
    def __init__(self):
        self.exchanges = {}  # {user_id: {exchange_id: exchange}}
    
    async def connect_exchange(self, user_id: str, exchange_id: str, api_key: str, secret_key: str, passphrase: str = None):
        """Connect to exchange with API keys"""
        try:
            if exchange_id not in self.SUPPORTED_EXCHANGES:
                raise ValueError(f"Exchange {exchange_id} not supported")
            
            exchange_class = self.SUPPORTED_EXCHANGES[exchange_id]
            exchange = exchange_class({
                'apiKey': api_key,
                'secret': secret_key,
                'password': passphrase if passphrase else None,
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            })
            
            # Test connection
            await exchange.load_markets()
            
            # Save connection
            if user_id not in self.exchanges:
                self.exchanges[user_id] = {}
            self.exchanges[user_id][exchange_id] = exchange
            
            logger.info(f"Connected to {exchange_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to {exchange_id}: {str(e)}")
            raise Exception(f"Connection failed: {str(e)}")
    
    async def get_balance(self, user_id: str, exchange_id: str) -> Dict:
        """Get balance on exchange"""
        try:
            exchange = self._get_exchange(user_id, exchange_id)
            balance = await exchange.fetch_balance()
            
            usdt_balance = balance.get('USDT', {})
            return {
                'exchange': exchange_id,
                'currency': 'USDT',
                'free': float(usdt_balance.get('free', 0)),
                'locked': float(usdt_balance.get('used', 0)),
                'total': float(usdt_balance.get('total', 0)),
                'updated_at': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error fetching balance: {str(e)}")
            return {'exchange': exchange_id, 'currency': 'USDT', 'free': 0, 'locked': 0, 'total': 0}
    
    async def get_ticker_price(self, exchange_id: str, symbol: str) -> float:
        """Get current price"""
        try:
            exchange_class = self.SUPPORTED_EXCHANGES[exchange_id]
            exchange = exchange_class({'enableRateLimit': True})
            ticker = await exchange.fetch_ticker(f"{symbol}/USDT")
            return ticker['last']
        except Exception as e:
            logger.error(f"Error fetching price: {str(e)}")
            raise
    
    async def get_price_history(self, symbol: str, interval: str = '1m', limit: int = 100, exchange_id: str = 'binance') -> List[Dict]:
        """Get price history for chart"""
        try:
            exchange = ccxt.binance({'enableRateLimit': True})
            ohlcv = await exchange.fetch_ohlcv(f"{symbol}/USDT", timeframe=interval, limit=limit)
            
            history = []
            for candle in ohlcv:
                history.append({
                    'timestamp': candle[0],
                    'time': datetime.fromtimestamp(candle[0] / 1000).strftime('%H:%M'),
                    'open': candle[1],
                    'high': candle[2],
                    'low': candle[3],
                    'close': candle[4],
                    'price': candle[4],
                    'volume': candle[5]
                })
            
            return history
        except Exception as e:
            logger.error(f"Error fetching history: {str(e)}")
            return []
    
    async def get_top_coins(self, limit: int = 10) -> List[Dict]:
        """Get top coins by volume"""
        try:
            exchange = ccxt.binance({'enableRateLimit': True})
            tickers = await exchange.fetch_tickers()
            
            usdt_pairs = {k: v for k, v in tickers.items() if '/USDT' in k and ':USDT' not in k}
            sorted_pairs = sorted(usdt_pairs.items(), key=lambda x: x[1].get('quoteVolume', 0), reverse=True)[:limit]
            
            coins = []
            for symbol, ticker in sorted_pairs:
                coin_symbol = symbol.split('/')[0]
                coins.append({
                    'symbol': coin_symbol,
                    'name': coin_symbol,
                    'price': ticker.get('last', 0),
                    'change': ticker.get('percentage', 0),
                    'volume': ticker.get('quoteVolume', 0)
                })
            
            return coins
        except Exception as e:
            logger.error(f"Error fetching top coins: {str(e)}")
            return []
    
    def _get_exchange(self, user_id: str, exchange_id: str):
        """Get exchange instance"""
        if user_id not in self.exchanges or exchange_id not in self.exchanges[user_id]:
            raise ValueError(f"Exchange {exchange_id} not connected")
        return self.exchanges[user_id][exchange_id]

# Global instance
exchange_service = ExchangeService()
