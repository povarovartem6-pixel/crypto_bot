import ccxt
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class WhaleTracker:
    def __init__(self, db):
        self.db = db
        self.exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
        # Монеты, за которыми следим
        self.coins = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'AVAX', 'LINK']
        self.last_processed_trade_id = {}
        # Порог крупной сделки в USDT (например, 500 000)
        self.threshold_usdt = 500_000

    def get_recent_trades(self, symbol):
        try:
            return self.exchange.fetch_trades(f'{symbol}/USDT', limit=50)
        except Exception as e:
            logger.error(f"Whale fetch error {symbol}: {e}")
            return []

    async def monitor(self, bot):
        while True:
            try:
                for coin in self.coins:
                    symbol = f'{coin}/USDT'
                    trades = self.get_recent_trades(symbol)
                    if not trades:
                        continue

                    for trade in trades:
                        trade_id = trade['id']
                        last_id = self.last_processed_trade_id.get(symbol)
                        
                        if last_id and trade_id <= last_id:
                            continue

                        cost = float(trade['price']) * float(trade['amount'])
                        
                        if cost >= self.threshold_usdt:
                            side = trade['side'] # 'buy' или 'sell'
                            side_ru = 'КУПИЛ' if side == 'buy' else 'ПРОДАЛ'
                            
                            if side == 'buy':
                                forecast = "Возможен локальный рост или пробой сопротивления."
                            else:
                                forecast = "Возможен локальный сброс или пробой поддержки."
                            
                            # Рассылаем только PRO-пользователям
                            users = self.db.get_all_users()
                            for u in users:
                                if u['tariff'] in ['pro', 'vip']:
                                    try:
                                        await bot.send_message(
                                            u['user_id'],
                                            f"🐋 <b>КИТ-АЛЕРТ: {coin}</b>\n\n"
                                            f"💰 Сумма: <b>${cost:,.0f}</b>\n"
                                            f"📊 Действие: <b>{side_ru}</b>\n\n"
                                            f"💡 <b>Что ожидать:</b> {forecast}\n\n"
                                            f"⏰ {datetime.now().strftime('%H:%M:%S')}",
                                            parse_mode='HTML'
                                        )
                                    except Exception:
                                        pass
                        
                        self.last_processed_trade_id[symbol] = trade_id

                await asyncio.sleep(60) # Проверяем раз в минуту
            except Exception as e:
                logger.error(f"Whale monitor error: {e}")
                await asyncio.sleep(60)
