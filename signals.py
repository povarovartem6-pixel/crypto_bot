import ccxt
import numpy as np
from datetime import datetime
from config import TAKER_FEE, SLIPPAGE, MIN_RR, MIN_EDGE, FUTURES_CONFIG
from indicators import AdvancedIndicators

TF_MAP = {'5м':'5m','15м':'15m','30м':'30m','1ч':'1h','4ч':'4h','1д':'1d'}

class SignalGenerator:
    def __init__(self, db):
        self.db = db
        self.ti = AdvancedIndicators()
        self.exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})

    def fetch(self, symbol, tf, limit=300):
        try: return self.exchange.fetch_ohlcv(symbol, tf, limit=limit)
        except Exception: return []

    def calculate_leverage(self, atr_pct):
        return int(np.clip(5 / (atr_pct + 0.1), FUTURES_CONFIG['min_leverage'], FUTURES_CONFIG['max_leverage']))

    def analyze(self, coin, timeframe):
        symbol = f'{coin}/USDT'
        tf = TF_MAP.get(timeframe, '1h')
        ohlcv = self.fetch(symbol, tf, 300)
        if len(ohlcv) < 50: return None

        r = self.ti.get_signal_data(ohlcv)
        if r['signal_type'] == 'NEUTRAL': return None

        price = r['price']
        atr = r['price'] * (r['atr_pct'] / 100)
        
        if r['signal_type'] == 'BUY':
            sl = price - atr * 1.5
            tp1 = price + atr * 2.0
            tp2 = price + atr * 3.5
            tp3 = price + atr * 5.0
        else:
            sl = price + atr * 1.5
            tp1 = price - atr * 2.0
            tp2 = price - atr * 3.5
            tp3 = price - atr * 5.0
            
        rr = abs(tp1 - price) / (abs(price - sl) + 1e-10)
        
        sig = {
            'coin': coin, 'symbol': symbol, 'timeframe': timeframe,
            'signal_type': r['signal_type'],
            'entry_price': float(price), 'stop_loss': float(sl),
            'target_prices': [float(tp1), float(tp2), float(tp3)],
            'risk_reward': float(rr), 'confidence': float(r['confidence']),
            'atr_pct': r['atr_pct']
        }
        sig['id'] = self.db.add_signal(**sig)
        return sig

    def scan(self, coins, timeframe):
        out = []
        for c in coins:
            try:
                s = self.analyze(c, timeframe)
                if s: out.append(s)
            except Exception: pass
        out.sort(key=lambda x: x['confidence'], reverse=True)
        return out

    def format(self, s, user_balance=1000, exchange_name='binance'):
        if s['signal_type'] == 'BUY':
            e_icon = '🟢📈'
            action_text = 'ЛОНГ (Покупка)'
            warning = ''
        else:
            e_icon = '🔴📉'
            action_text = 'ШОРТ (Продажа)'
            warning = '\n⚠️ <b>Внимание:</b> Шорт - это высокий риск! Плечо не выше 3x, стоп строго обязателен.'

        atr_pct = s.get('atr_pct', 1.0)
        rec_lev = self.calculate_leverage(atr_pct)
        
        risk_usdt = user_balance * FUTURES_CONFIG['risk_per_trade']
        risk_percent = abs(s['entry_price'] - s['stop_loss']) / s['entry_price']
        rec_size = (risk_usdt / (risk_percent * rec_lev)) if risk_percent > 0 else 0

        txt = f"""
{e_icon} <b>{s['signal_type']} | {s['coin']}/USDT (Фьючерсы)</b>
━━━━━━━━━━━━━━━━━━━━
┃ 🎯 <b>Сделка:</b> {action_text}
┃ ⏱ <b>ТФ:</b> {s['timeframe']} | <b>R:R</b> 1:{s['risk_reward']:.1f}
┃ 📊 <b>Уверенность:</b> {s['confidence']:.0f}%
━━━━━━━━━━━━━━━━━━━━
<blockquote>💰 <b>Вход:</b> ${s['entry_price']:.5g}
🛑 <b>Стоп-лосс:</b> ${s['stop_loss']:.5g}
🎯 <b>Цель 1 (TP1):</b> ${s['target_prices'][0]:.5g}
🎯 <b>Цель 2 (TP2):</b> ${s['target_prices'][1]:.5g}</blockquote>

⚙️ <b>Рекомендации по фьючерсам:</b>
┃ Плечо: <b>{max(1, rec_lev-2)}x - {rec_lev+3}x</b> (оптимально {rec_lev}x)
┃ Размер позиции: <b>${rec_size:.2f}</b>{warning}
"""
        return txt
