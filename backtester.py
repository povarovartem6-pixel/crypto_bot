import ccxt
import numpy as np
from datetime import datetime
from indicators import AdvancedIndicators

class Backtester:
    def __init__(self):
        self.exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
        self.ti = AdvancedIndicators()

    def fetch_history(self, symbol, tf, limit=1000):
        try: return self.exchange.fetch_ohlcv(symbol, tf, limit=limit)
        except: return []

    def run(self, coin, timeframe='15m', forward_candles=20):
        """Прогоняет историю и считает, сколько сигналов сработало в плюс"""
        symbol = f'{coin}/USDT'
        tf_map = {'5м':'5m','15м':'15m','30м':'30m','1ч':'1h','4ч':'4h','1д':'1d'}
        tf = tf_map.get(timeframe, '15m')
        
        data = self.fetch_history(symbol, tf, 1000)
        if len(data) < 300: return None

        wins, losses, total = 0, 0, 0
        
        # Прогоняем по истории (шаг 10 свечей, чтобы не грузить CPU)
        for i in range(250, len(data) - forward_candles, 10):
            slice_data = data[:i+1]
            # Для простоты в бэктесте используем только 15м тренд (чтобы не делать 1000 запросов)
            arr = np.array(slice_data, dtype=float)
            
            # Упрощенная проверка для бэктеста
            c = arr[:,4]
            ema9 = self.ti.ema(c, 9); ema21 = self.ti.ema(c, 21)
            rsi_v = self.ti.rsi(c, 14)[-1]
            
            signal = 'NEUTRAL'
            if ema9[-1] > ema21[-1] and 40 < rsi_v < 65: signal = 'BUY'
            elif ema9[-1] < ema21[-1] and 35 < rsi_v < 60: signal = 'SELL'
            
            if signal == 'NEUTRAL': continue
            
            entry = c[-1]
            atr = self.ti.atr(arr[:,2], arr[:,3], c)[-1]
            
            if signal == 'BUY':
                sl, tp1 = entry - atr*1.5, entry + atr*2.0
            else:
                sl, tp1 = entry + atr*1.5, entry - atr*2.0
            
            # Смотрим, что было дальше
            future = data[i+1 : i+1+forward_candles]
            hit_tp, hit_sl = False, False
            
            for candle in future:
                h, l = candle[2], candle[3]
                if signal == 'BUY':
                    if l <= sl: hit_sl = True; break
                    if h >= tp1: hit_tp = True; break
                else:
                    if h >= sl: hit_sl = True; break
                    if l <= tp1: hit_tp = True; break
            
            total += 1
            if hit_tp: wins += 1
            elif hit_sl: losses += 1

        winrate = (wins / total * 100) if total > 0 else 0
        return {
            'total': total,
            'wins': wins,
            'losses': losses,
            'winrate': winrate
        }
