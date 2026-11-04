import ccxt, asyncio, logging
from database import get_conn, Database

logger = logging.getLogger(__name__)

class PaperTrader:
    def __init__(self, db): self.db = db
    def auto_open(self, user_id, signal, custom_size=None):
        user = self.db.get_user(user_id)
        if not user: return
        if custom_size:
            size = custom_size / signal['entry_price']
        else:
            balance = user.get('balance_usdt', 1000.0)
            risk_usdt = balance * 0.01
            risk_per_unit = abs(signal['entry_price'] - signal['stop_loss'])
            size = risk_usdt / risk_per_unit if risk_per_unit > 0 else 0
        if size > 0:
            self.db.open_trade(user_id, signal['id'], signal['entry_price'], signal['stop_loss'],
                               signal['target_prices'][0], signal['target_prices'][1],
                               signal['target_prices'][2], size)

class TradeTracker:
    def __init__(self, db):
        self.db = db
        self.exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})

    def current_price(self, symbol):
        try: return float(self.exchange.fetch_ticker(symbol)['last'])
        except: return None

    async def monitor(self, bot):
        notified_tp1, notified_tp2, warned_sl = set(), set(), set()
        while True:
            try:
                trades = self.db.get_open_trades()
                for t in trades:
                    conn = get_conn()
                    row = conn.execute('SELECT coin, signal_type FROM signals WHERE id=?', (t['signal_id'],)).fetchone()
                    conn.close()
                    if not row: continue
                    
                    coin, side = row['coin'], row['signal_type']
                    price = self.current_price(f'{coin}/USDT')
                    if not price: continue

                    entry, sl, tp1, tp2 = t['entry_price'], t['stop_loss'], t['tp1'], t['tp2']
                    trade_id = t['id']

                    if side == 'BUY':
                        hit_sl, hit_tp1, hit_tp2 = price <= sl, price >= tp1, price >= tp2
                    else:
                        hit_sl, hit_tp1, hit_tp2 = price >= sl, price <= tp1, price <= tp2

                    if hit_sl:
                        pnl = (price - entry) / entry * t['size'] if side == 'BUY' else (entry - price) / entry * t['size']
                        self.db.close_trade(trade_id, price, pnl, 'SL hit')
                        try: await bot.send_message(t['user_id'], f"🛑 <b>Стоп-лосс сработал</b>\n{coin} | Убыток: {pnl:.2f} USDT\n\n<i>Это часть торговли.</i>", parse_mode='HTML')
                        except: pass
                        continue

                    if hit_tp2 and trade_id not in notified_tp2:
                        pnl = abs(tp2 - entry) / entry * t['size']
                        self.db.close_trade(trade_id, tp2, pnl, 'TP2 hit')
                        notified_tp2.add(trade_id)
                        try: await bot.send_message(t['user_id'], f"🏆 <b>Цель TP2 достигнута!</b>\n{coin} | Прибыль: +{pnl:.2f} USDT", parse_mode='HTML')
                        except: pass

                    elif hit_tp1 and trade_id not in notified_tp1:
                        notified_tp1.add(trade_id)
                        try: await bot.send_message(t['user_id'], f"🎯 <b>Цель TP1 достигнута!</b>\n{coin}\n1. Закройте 50%.\n2. Стоп в безубыток.", parse_mode='HTML')
                        except: pass
                        conn = get_conn()
                        conn.execute('UPDATE trades SET stop_loss=? WHERE id=?', (entry, trade_id))
                        conn.commit(); conn.close()
                        
                    dist_to_sl = abs(price - sl) / price * 100
                    if dist_to_sl < 0.3 and trade_id not in warned_sl:
                        warned_sl.add(trade_id)
                        try: await bot.send_message(t['user_id'], f"⚠️ <b>Цена близко к стопу!</b>\n{coin}\n<i>Не двигайте стоп вниз.</i>", parse_mode='HTML')
                        except: pass

                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Tracker error: {e}")
                await asyncio.sleep(30)
