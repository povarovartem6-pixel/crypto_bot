import pandas as pd
import numpy as np
from advanced_analysis import AdvancedAnalysis

class AdvancedIndicators:
    @staticmethod
    def ema(p, n): return pd.Series(p).ewm(span=n, adjust=False).mean().values
    
    @staticmethod
    def rsi(p, n=14):
        d = np.diff(p); g = np.where(d > 0, d, 0); l = np.where(d < 0, -d, 0)
        ag = pd.Series(g).ewm(alpha=1/n, adjust=False).mean().values
        al = pd.Series(l).ewm(alpha=1/n, adjust=False).mean().values
        return np.concatenate([[50], 100 - 100/(1+ag/(al+1e-10))])

    @staticmethod
    def adx(h, l, c, n=14):
        up = h[1:]-h[:-1]; dn = l[:-1]-l[1:]
        pdm = np.where((up > dn) & (up > 0), up, 0)
        mdm = np.where((dn > up) & (dn > 0), dn, 0)
        tr = np.maximum.reduce([h[1:]-l[1:], np.abs(h[1:]-c[:-1]), np.abs(l[1:]-c[:-1])])
        atr_v = pd.Series(tr).ewm(alpha=1/n, adjust=False).mean().values
        pdi = 100 * pd.Series(pdm).ewm(alpha=1/n, adjust=False).mean().values / (atr_v + 1e-10)
        mdi = 100 * pd.Series(mdm).ewm(alpha=1/n, adjust=False).mean().values / (atr_v + 1e-10)
        dx = 100 * np.abs(pdi - mdi) / (pdi + mdi + 1e-10)
        return np.concatenate([[25], pd.Series(dx).ewm(alpha=1/n, adjust=False).mean().values])

    @staticmethod
    def atr(h, l, c, n=14):
        tr = np.maximum.reduce([h[1:]-l[1:], np.abs(h[1:]-c[:-1]), np.abs(l[1:]-c[:-1])])
        a = pd.Series(tr).ewm(alpha=1/n, adjust=False).mean().values
        return np.concatenate([[tr[0] if len(tr) else 0], a])

    @staticmethod
    def supertrend(h, l, c, n=10, m=3.0):
        atr = AdvancedIndicators.atr(h, l, c, n)
        hl2 = (h + l) / 2
        up = hl2 + m*atr; lo = hl2 - m*atr
        d = np.ones(len(c))
        for i in range(1, len(c)):
            if c[i] > up[i-1]: d[i] = 1
            elif c[i] < lo[i-1]: d[i] = -1
            else: d[i] = d[i-1]
        return d

    def get_confluence_score(self, ohlcv_15m, ohlcv_1h, ohlcv_4h, btc_trend, fear_greed, funding_rate):
        """
        Главная функция. Считает баллы для покупки/продажи с учетом всех новых фильтров.
        """
        arr = np.array(ohlcv_15m, dtype=float)
        o, h, l, c, v = arr[:,1], arr[:,2], arr[:,3], arr[:,4], arr[:,5]
        
        ema9 = self.ema(c, 9); ema21 = self.ema(c, 21); ema50 = self.ema(c, 50)
        rsi_v = self.rsi(c, 14)
        st = self.supertrend(h, l, c)[-1]
        adx_v = self.adx(h, l, c)[-1]
        
        # Новые проверки
        divergence = AdvancedAnalysis.check_divergence(c, rsi_v)
        structure = AdvancedAnalysis.check_market_structure(h, l, c)
        poc = AdvancedAnalysis.get_volume_profile(h, l, c, v)
        
        vol_ratio = v[-1] / (np.mean(v[-20:]) + 1e-10)
        
        c1h = np.array(ohlcv_1h, dtype=float)[:,4]
        c4h = np.array(ohlcv_4h, dtype=float)[:,4]
        ema200_1h = self.ema(c1h, 200)[-1] if len(c1h) > 200 else c1h[-1]
        ema200_4h = self.ema(c4h, 200)[-1] if len(c4h) > 200 else c4h[-1]

        # === СИСТЕМА БАЛЛОВ ===
        buy_score, sell_score = 0, 0
        
        if ema9[-1] > ema21[-1] > ema50[-1]: buy_score += 1
        elif ema9[-1] < ema21[-1] < ema50[-1]: sell_score += 1
        
        if st == 1: buy_score += 1
        else: sell_score += 1
        
        if 40 < rsi_v[-1] < 65: buy_score += 1
        elif 35 < rsi_v[-1] < 60: sell_score += 1
        
        if c1h[-1] > ema200_1h: buy_score += 2
        else: sell_score += 2
        
        if c4h[-1] > ema200_4h: buy_score += 3
        else: sell_score += 3

        if vol_ratio > 1.3: 
            if c[-1] > o[-1]: buy_score += 1
            else: sell_score += 1
            
        if adx_v > 25:
            if ema9[-1] > ema21[-1]: buy_score += 1
            else: sell_score += 1
            
        # Дивергенции
        if divergence == 'bullish': buy_score += 2
        elif divergence == 'bearish': sell_score += 2
            
        # Структура (BOS)
        if structure == 'bullish_bos': buy_score += 2
        elif structure == 'bearish_bos': sell_score += 2
            
        # Фильтр Биткоина
        if btc_trend == "down" and buy_score > sell_score: buy_score -= 3
        elif btc_trend == "up" and sell_score > buy_score: sell_score -= 3
        
        # Fear & Greed (контр-индикатор)
        if fear_greed < 25: buy_score += 1
        elif fear_greed > 75: sell_score += 1
        
        # Funding Rate (если все в лонгах, ищем шорт)
        if funding_rate > 0.05: sell_score += 1
        elif funding_rate < -0.05: buy_score += 1

        max_score = 16  # Обновили максимум
        signal_type = 'NEUTRAL'
        confidence = 0
        rating = "C"
        
        # Порог входа - минимум 11 из 16
        if buy_score >= 11:
            signal_type = 'BUY'
            confidence = int((buy_score / max_score) * 100)
            rating = "A+" if buy_score >= 14 else "B"
        elif sell_score >= 11:
            signal_type = 'SELL'
            confidence = int((sell_score / max_score) * 100)
            rating = "A+" if sell_score >= 14 else "B"
            
        if adx_v < 20: signal_type = 'NEUTRAL'

        return {
            'signal_type': signal_type, 'confidence': confidence, 'rating': rating,
            'price': float(c[-1]), 'atr_pct': float(self.atr(h,l,c)[-1] / c[-1] * 100),
            'poc': poc, 'buy_score': buy_score, 'sell_score': sell_score
        }
