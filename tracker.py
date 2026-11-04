import ccxt, asyncio
from database import get_conn

class PaperTrader:
    def __init__(self, db): self.db = db
    def auto_open(self, user_id, signal):
        user = self.db.get_user(user_id)
        if not user: return
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
        notified_tp1, notified_tp2 = set(), set()
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
                        try: await bot.send_message(t['user_id'], f"🛑 <b>Стоп-лосс</b>\n{coin} | Убыток: {pnl:.2f} USDT", parse_mode='HTML')
                        except: pass
                    elif hit_tp2 and trade_id not in notified_tp2:
                        pnl = abs(tp2 - entry) / entry * t['size']
                        self.db.close_trade(trade_id, tp2, pnl, 'TP2 hit')
                        notified_tp2.add(trade_id)
                        try: await bot.send_message(t['user_id'], f"🏆 <b>Цель TP2!</b>\n{coin} | Прибыль: +{pnl:.2f} USDT", parse_mode='HTML')
                        except: pass
                    elif hit_tp1 and trade_id not in notified_tp1:
                        notified_tp1.add(trade_id)
                        try: await bot.send_message(t['user_id'], f"🎯 <b>Цель TP1!</b>\n{coin}\nЗакройте 50% и переведите стоп в БУ.", parse_mode='HTML')
                        except: pass
                        conn = get_conn()
                        conn.execute('UPDATE trades SET stop_loss=? WHERE id=?', (entry, trade_id))
                        conn.commit(); conn.close()
                await asyncio.sleep(30)
            except Exception: await asyncio.sleep(30)
