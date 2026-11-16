import ccxt, asyncio, logging
from datetime import datetime
from database import get_conn

logger = logging.getLogger(__name__)

class PaperTrader:
    def __init__(self, db): self.db = db
    def auto_open(self, user_id, signal):
        user = self.db.get_user(user_id)
        if not user: return
        balance = user.get('balance_usdt', 1000.0)
        
        if signal['confidence'] >= 80: risk_pct = 0.02
        elif signal['confidence'] >= 60: risk_pct = 0.01
        else: risk_pct = 0.005
        
        risk_usdt = balance * risk_pct
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
        self.notified_tp1 = set()
        self.notified_tp2 = set()
        self.stuck_warned = set()
        self.trade_open_time = {}

    def current_price(self, symbol):
        try: return float(self.exchange.fetch_ticker(symbol)['last'])
        except Exception: return None

    async def monitor(self, bot):
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
                    current_sl = t['stop_loss']

                    if trade_id not in self.trade_open_time:
                        self.trade_open_time[trade_id] = datetime.now()
                    time_in_trade = (datetime.now() - self.trade_open_time[trade_id]).total_seconds() / 60
                    
                    if time_in_trade > 120 and abs(price - entry) / entry * 100 < 0.3 and trade_id not in self.stuck_warned:
                        self.stuck_warned.add(trade_id)
                        try: await bot.send_message(t['user_id'], f"😴 <b>Сделка по {coin} стоит на месте 2 часа.</b>", parse_mode='HTML')
                        except: pass

                    if side == 'BUY':
                        hit_sl = price <= current_sl
                        hit_tp1 = price >= tp1
                        hit_tp2 = price >= tp2
                        
                        if price >= entry + (tp1 - entry) * 0.5 and current_sl < entry:
                            conn = get_conn()
                            conn.execute('UPDATE trades SET stop_loss=? WHERE id=?', (entry, trade_id))
                            conn.commit(); conn.close()
                            try: await bot.send_message(t['user_id'], f"🛡 <b>Трейлинг-стоп по {coin}</b>\nСтоп передвинут в безубыток!", parse_mode='HTML')
                            except: pass
                            
                    else:
                        hit_sl = price >= current_sl
                        hit_tp1 = price <= tp1
                        hit_tp2 = price <= tp2
                        
                        if price <= entry - (entry - tp1) * 0.5 and current_sl > entry:
                            conn = get_conn()
                            conn.execute('UPDATE trades SET stop_loss=? WHERE id=?', (entry, trade_id))
                            conn.commit(); conn.close()
                            try: await bot.send_message(t['user_id'], f"🛡 <b>Трейлинг-стоп по {coin}</b>\nСтоп передвинут в безубыток!", parse_mode='HTML')
                            except: pass

                    if hit_sl:
                        self.db.close_trade(trade_id, price, 0, 'Стоп-лосс')
                        try: await bot.send_message(t['user_id'], f"🛑 <b>Стоп-лосс сработал по {coin}</b>", parse_mode='HTML')
                        except: pass
                        continue

                    if hit_tp2 and trade_id not in self.notified_tp2:
                        self.db.close_trade(trade_id, tp2, 0, 'Цель TP2 достигнута')
                        self.notified_tp2.add(trade_id)
                        try: await bot.send_message(t['user_id'], f"🏆 <b>Цель TP2 достигнута по {coin}!</b>", parse_mode='HTML')
                        except: pass

                    elif hit_tp1 and trade_id not in self.notified_tp1:
                        self.notified_tp1.add(trade_id)
                        try: await bot.send_message(t['user_id'], f"🎯 <b>Цель TP1 достигнута по {coin}!</b>\nЗакройте 50% и переведите стоп в БУ.", parse_mode='HTML')
                        except: pass
                        
                        conn = get_conn()
                        conn.execute('UPDATE trades SET stop_loss=? WHERE id=?', (entry, trade_id))
                        conn.commit(); conn.close()

                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Tracker error: {e}")
                await asyncio.sleep(30)
