import ccxt
import numpy as np
import random
from datetime import datetime
from config import FUTURES_CONFIG
from indicators import AdvancedIndicators
import requests

TF_MAP = {'5м':'5m','15м':'15m','30м':'30m','1ч':'1h','4ч':'4h','1д':'1d'}

class SignalGenerator:
    def __init__(self, db):
        self.db = db
        self.ti = AdvancedIndicators()
        self.exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})

    def fetch(self, symbol, tf, limit=250):
        try: return self.exchange.fetch_ohlcv(symbol, tf, limit=limit)
        except Exception: return []

    def get_btc_trend(self):
        try:
            btc_1h = self.fetch('BTC/USDT', '1h', 50)
            if not btc_1h: return "neutral"
            closes = np.array(btc_1h, dtype=float)[:,4]
            ema20 = self.ti.ema(closes, 20)[-1]
            ema50 = self.ti.ema(closes, 50)[-1]
            if closes[-1] > ema20 and ema20 > ema50: return "up"
            elif closes[-1] < ema20 and ema20 < ema50: return "down"
        except: pass
        return "neutral"

    def get_fear_greed(self):
        try:
            return int(requests.get('https://api.alternative.me/fng/', timeout=5).json()['data'][0]['value'])
        except: return 50

    def get_funding_rate(self, symbol):
        try:
            return float(self.exchange.fetch_funding_rate(symbol)['fundingRate']) * 100 # В процентах
        except: return 0.0

    def analyze(self, coin, timeframe):
        symbol = f'{coin}/USDT'
        tf = TF_MAP.get(timeframe, '15m')
        
        ohlcv_15m = self.fetch(symbol, tf, 250)
        ohlcv_1h = self.fetch(symbol, '1h', 250)
        ohlcv_4h = self.fetch(symbol, '4h', 250)
        
        if len(ohlcv_15m) < 50 or len(ohlcv_1h) < 50 or len(ohlcv_4h) < 50: return None

        btc_trend = self.get_btc_trend()
        fg = self.get_fear_greed()
        fr = self.get_funding_rate(symbol)
        
        r = self.ti.get_confluence_score(ohlcv_15m, ohlcv_1h, ohlcv_4h, btc_trend, fg, fr)
        
        if r['signal_type'] == 'NEUTRAL': return None

        price = r['price']
        atr = price * (r['atr_pct'] / 100)
        
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
            'signal_type': r['signal_type'], 'entry_price': float(price), 'stop_loss': float(sl),
            'target_prices': [float(tp1), float(tp2), float(tp3)],
            'risk_reward': float(rr), 'confidence': float(r['confidence']), 'atr_pct': r['atr_pct'],
            'rating': r['rating']
        }
        sig['id'] = self.db.add_signal(**sig)
        return sig

    def scan(self, coins, timeframe):
        out = []
        random.shuffle(coins) 
        for c in coins:
            try:
                s = self.analyze(c, timeframe)
                if s: out.append(s)
            except Exception: pass
        out.sort(key=lambda x: (x['rating'] == 'A+', x['confidence']), reverse=True)
        return out

    def format(self, s, user_balance=1000):
        icon = '🟢📈' if s['signal_type'] == 'BUY' else '🔴📉'
        action = 'ЛОНГ' if s['signal_type'] == 'BUY' else 'ШОРТ'
        
        confidence = s['confidence']
        rating = s.get('rating', 'B')
        
        if confidence >= 80: risk_pct = 0.02
        elif confidence >= 60: risk_pct = 0.01
        else: risk_pct = 0.005

        risk_usdt = user_balance * risk_pct
        sl_distance = abs(s['entry_price'] - s['stop_loss']) / s['entry_price']
        rec_size = (risk_usdt / sl_distance) if sl_distance > 0 else 0
        rec_lev = int(np.clip(5 / (s.get('atr_pct', 1.0) + 0.1), 1, 10))
        
        min_lev = max(1, rec_lev - 1)
        max_lev = min(10, rec_lev + 1)
        
        rating_text = "🔥 Снайпер (A+)" if rating == "A+" else "⚡ Хороший (B)"

        return f"""
{icon} <b>{s['signal_type']} | {s['coin']}/USDT</b>
━━━━━━━━━━━━━━━━━━━━
🎯 <b>Сделка:</b> {action}
📊 <b>Рейтинг:</b> {rating_text}
⏱ <b>ТФ:</b> {s['timeframe']} | R:R 1:{s['risk_reward']:.1f}

<blockquote>💰 <b>Вход:</b> ${s['entry_price']:.5g}
🛑 <b>Стоп:</b> ${s['stop_loss']:.5g}
🎯 <b>TP1:</b> ${s['target_prices'][0]:.5g}
🎯 <b>TP2:</b> ${s['target_prices'][1]:.5g}</blockquote>

⚙️ <b>Рекомендации:</b>
Плечо: <b>{min_lev}x - {max_lev}x</b>
Позиция: <b>${rec_size:.2f}</b>
⚠️ <i>Убыток при стопе: ${risk_usdt:.2f}</i>
"""
