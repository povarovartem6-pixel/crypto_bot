import numpy as np

class AdvancedAnalysis:
    @staticmethod
    def find_swings(prices, left=5, right=5):
        """Находит локальные экстремумы (для дивергенций)"""
        highs, lows = [], []
        for i in range(left, len(prices) - right):
            window = prices[i - left:i + right + 1]
            if prices[i] == max(window): highs.append((i, prices[i]))
            if prices[i] == min(window): lows.append((i, prices[i]))
        return highs, lows

    @staticmethod
    def check_divergence(prices, rsi_values):
        """Ищет бычью или медвежью дивергенцию RSI"""
        if len(prices) < 30: return 'none'
        highs, lows = AdvancedAnalysis.find_swings(prices[-30:])
        
        # Бычья дивергенция: цена делает Low ниже, а RSI делает Low выше
        if len(lows) >= 2:
            p1, p2 = lows[-2], lows[-1]
            r1, r2 = rsi_values[-30 + p1[0]], rsi_values[-30 + p2[0]]
            if p2[1] < p1[1] and r2 > r1:
                return 'bullish'
                
        # Медвежья дивергенция: цена делает High выше, а RSI делает High ниже
        if len(highs) >= 2:
            p1, p2 = highs[-2], highs[-1]
            r1, r2 = rsi_values[-30 + p1[0]], rsi_values[-30 + p2[0]]
            if p2[1] > p1[1] and r2 < r1:
                return 'bearish'
        return 'none'

    @staticmethod
    def get_volume_profile(highs, lows, closes, volumes, bins=20):
        """Строит профиль объема и находит Point of Control (POC) - цену с макс. объемом"""
        if len(closes) < 20: return None
        lo, hi = np.min(lows), np.max(highs)
        if hi == lo: return closes[-1]
        
        edges = np.linspace(lo, hi, bins + 1)
        centers = (edges[:-1] + edges[1:]) / 2
        profile = np.zeros(bins)
        
        for i, c in enumerate(closes):
            idx = min(bins - 1, int((c - lo) / (hi - lo) * bins))
            profile[idx] += volumes[i]
            
        poc_price = centers[np.argmax(profile)]
        return poc_price

    @staticmethod
    def check_market_structure(highs, lows, closes):
        """Проверка слома структуры (BOS) - простейший SMC"""
        if len(closes) < 20: return 'neutral'
        recent_high = max(highs[-20:-5])
        recent_low = min(lows[-20:-5])
        
        if closes[-1] > recent_high: return 'bullish_bos'
        if closes[-1] < recent_low: return 'bearish_bos'
        return 'neutral'
