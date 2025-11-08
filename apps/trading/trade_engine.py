# ===== apps/trading/trade_engine.py =====
import asyncio
from datetime import datetime
from typing import Dict
from .models import Trade, BotLog
import logging

logger = logging.getLogger(__name__)

class TradeEngine:
    """Trading bot engine"""
    
    def __init__(self):
        self.active_bots = {}  # {user_id: is_running}
        self.bot_tasks = {}  # {user_id: task}
        self.trade_params = {}  # {user_id: params}
    
    async def start_trading(self, user, settings, params):
        """Start trading bot"""
        user_id = str(user.id)
        
        if user_id in self.active_bots and self.active_bots[user_id]:
            raise ValueError("Bot is already running")
        
        self.trade_params[user_id] = params
        self.active_bots[user_id] = True
        
        # Create log
        BotLog.objects.create(
            user=user,
            log_type='success',
            message='🚀 Бот запущен! Начинаю мониторинг рынка...'
        )
        
        # Start trading loop
        if settings['trade_type'] == 'arbitrage':
            task = asyncio.create_task(self._arbitrage_loop(user_id, user))
        else:
            task = asyncio.create_task(self._margin_trading_loop(user_id, user))
        
        self.bot_tasks[user_id] = task
        logger.info(f"Trading bot started for user {user_id}")
    
    async def stop_trading(self, user):
        """Stop trading bot"""
        user_id = str(user.id)
        
        if user_id in self.active_bots:
            self.active_bots[user_id] = False
            
            if user_id in self.bot_tasks:
                self.bot_tasks[user_id].cancel()
                try:
                    await self.bot_tasks[user_id]
                except asyncio.CancelledError:
                    pass
                del self.bot_tasks[user_id]
            
            BotLog.objects.create(
                user=user,
                log_type='info',
                message='⏸️ Бот остановлен. Открытые позиции сохранены.'
            )
            logger.info(f"Trading bot stopped for user {user_id}")
    
    async def _arbitrage_loop(self, user_id, user):
        """Arbitrage trading loop"""
        while self.active_bots.get(user_id, False):
            try:
                BotLog.objects.create(
                    user=user,
                    log_type='search',
                    message='🔍 Анализирую спреды между биржами...'
                )
                
                # TODO: Implement real arbitrage logic
                await asyncio.sleep(15)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in arbitrage loop: {str(e)}")
                BotLog.objects.create(
                    user=user,
                    log_type='error',
                    message=f'❌ Ошибка: {str(e)}'
                )
                await asyncio.sleep(10)
    
    async def _margin_trading_loop(self, user_id, user):
        """Margin trading loop"""
        while self.active_bots.get(user_id, False):
            try:
                BotLog.objects.create(
                    user=user,
                    log_type='search',
                    message='📈 Анализирую графики для входа в позицию...'
                )
                
                # TODO: Implement real margin trading logic
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in margin trading loop: {str(e)}")
                await asyncio.sleep(10)
    
    def get_status(self, user_id):
        """Get trading status"""
        return {
            'is_running': self.active_bots.get(user_id, False),
            'active_trades_count': 0,  # TODO
            'total_trades': 0,  # TODO
            'total_pnl': 0,  # TODO
            'pnl_percent': 0,  # TODO
        }

# Global instance
trade_engine = TradeEngine()
