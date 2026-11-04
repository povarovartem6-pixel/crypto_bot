import pandas as pd, numpy as np

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

    def get_signal_data(self, ohlcv):
        arr = np.array(ohlcv, dtype=float)
        o, h, l, c = arr[:,1], arr[:,2], arr[:,3], arr[:,4]
        
        ema9 = self.ema(c, 9); ema21 = self.ema(c, 21); ema50 = self.ema(c, 50)
        rsi_v = self.rsi(c, 14)
        st = self.supertrend(h, l, c)
        price = c[-1]
        
        bull, bear = 0, 0
        if ema9[-1] > ema21[-1] > ema50[-1]: bull += 2
        elif ema9[-1] < ema21[-1] < ema50[-1]: bear += 2
        
        if st[-1] == 1: bull += 2
        else: bear += 2
        
        if 40 < rsi_v[-1] < 65: bull += 1
        elif 35 < rsi_v[-1] < 60: bear += 1
        if rsi_v[-1] < 30: bull += 2
        if rsi_v[-1] > 70: bear += 2
        
        sig_type = 'NEUTRAL'
        conf = 0
        if bull >= 5 and bull > bear:
            sig_type = 'BUY'; conf = min(95, bull * 15)
        elif bear >= 5 and bear > bull:
            sig_type = 'SELL'; conf = min(95, bear * 15)
            
        return {
            'signal_type': sig_type, 'confidence': conf, 'price': float(price),
            'atr_pct': float(self.atr(h,l,c)[-1] / price * 100)
        }
