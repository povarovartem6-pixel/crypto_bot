import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import sqlite3
from dataclasses import dataclass
from enum import Enum

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
BOT_TOKEN = "8588787774:AAHLkHR4BXSPFQLjVSqOLar6SdloT2ORbro"
OWNER_ID = 8361478292
BINANCE_API = "https://api.binance.com/api/v3"
COINGECKO_API = "https://api.coingecko.com/api/v3"
FEAR_GREED_API = "https://api.alternative.me/fng/"

# Список криптовалют
CRYPTOCURRENCIES = {
    # Топ-20
    "BTC": "Bitcoin", "ETH": "Ethereum", "BNB": "BNB", "SOL": "Solana",
    "XRP": "XRP", "ADA": "Cardano", "DOGE": "Dogecoin", "AVAX": "Avalanche",
    "DOT": "Polkadot", "LINK": "Chainlink", "MATIC": "Polygon", "UNI": "Uniswap",
    "ATOM": "Cosmos", "LTC": "Litecoin", "BCH": "Bitcoin Cash", "NEAR": "NEAR Protocol",
    "ALGO": "Algorand", "VET": "VeChain", "ICP": "Internet Computer", "FIL": "Filecoin",
    # DeFi
    "AAVE": "Aave", "COMP": "Compound", "MKR": "Maker", "SNX": "Synthetix",
    "CRV": "Curve DAO", "SUSHI": "SushiSwap", "CAKE": "PancakeSwap", "1INCH": "1inch",
    "BAL": "Balancer", "YFI": "yearn.finance", "LDO": "Lido DAO", "RPL": "Rocket Pool",
    "GMX": "GMX", "DYDX": "dYdX", "PERP": "Perpetual Protocol", "GNS": "Gains Network",
    # Layer 1/2
    "APT": "Aptos", "ARB": "Arbitrum", "OP": "Optimism", "SUI": "Sui",
    "SEI": "Sei", "TIA": "Celestia", "INJ": "Injective", "TON": "Toncoin",
    "TRX": "TRON", "EGLD": "MultiversX", "HBAR": "Hedera", "FTM": "Fantom",
    "MINA": "Mina Protocol", "KAS": "Kaspa", "IMX": "Immutable X",
    # Meme
    "SHIB": "Shiba Inu", "PEPE": "Pepe", "FLOKI": "Floki", "BONK": "Bonk",
    "WIF": "dogwifhat", "MEME": "Memecoin", "TURBO": "Turbo", "BRETT": "Brett",
    # AI/Data
    "GRT": "The Graph", "OCEAN": "Ocean Protocol", "FET": "Fetch.ai", "AGIX": "SingularityNET",
    "RNDR": "Render Token", "THETA": "Theta Network", "AR": "Arweave", "TAO": "Bittensor",
    # Gaming
    "SAND": "The Sandbox", "MANA": "Decentraland", "AXS": "Axie Infinity", "GALA": "Gala",
    "ENJ": "Enjin Coin", "ILV": "Illuvium", "MAGIC": "Magic", "RON": "Ronin",
    # Exchange
    "OKB": "OKB", "KCS": "KuCoin Token", "HT": "Huobi Token", "GT": "GateToken",
    "CRO": "Cronos", "LEO": "UNUS SED LEO", "BGB": "Bitget Token",
    # Infrastructure
    "BAND": "Band Protocol", "API3": "API3", "TRB": "Tellor", "PYTH": "Pyth Network",
    "ROSE": "Oasis Network", "AKT": "Akash Network",
    # Privacy
    "XMR": "Monero", "ZEC": "Zcash", "DASH": "Dash", "SCRT": "Secret",
    # Другие
    "XTZ": "Tezos", "EOS": "EOS", "IOTA": "IOTA", "NEO": "Neo",
    "QTUM": "Qtum", "ZIL": "Zilliqa", "KAVA": "Kava", "WAVES": "Waves",
    "CELO": "Celo", "SKL": "SKALE"
}

@dataclass
class TradeSignal:
    symbol: str
    name: str
    signal_type: str  # "LONG" or "SHORT"
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    risk_reward_ratio: float
    timeframe: str = "24h"
    technical_score: float = 0
    volume_24h: float = 0
    potential_profit: float = 0

class Database:
    def __init__(self, db_path: str = "crypto_signals.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    is_successful BOOLEAN
                )
            ''')
            
            conn.commit()
    
    def save_signal(self, signal: TradeSignal):
        """Сохранение сигнала"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO signals 
                (symbol, signal_type, entry_price, stop_loss, take_profit, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal.symbol,
                signal.signal_type,
                signal.entry_price,
                signal.stop_loss,
                signal.take_profit,
                signal.confidence,
                datetime.now().isoformat()
            ))
            conn.commit()
    
    def get_stats(self) -> Dict:
        """Получение статистики"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN signal_type = 'LONG' THEN 1 ELSE 0 END) as longs,
                    SUM(CASE WHEN signal_type = 'SHORT' THEN 1 ELSE 0 END) as shorts,
                    AVG(confidence) as avg_conf
                FROM signals
            ''')
            result = cursor.fetchone()
            
            return {
                "total": result[0] or 0,
                "longs": result[1] or 0,
                "shorts": result[2] or 0,
                "avg_confidence": result[3] or 0
            }

class CryptoAnalyzer:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.fear_greed_index = 50
        self.btc_dominance = 50
    
    async def init_session(self):
        """Инициализация HTTP сессии"""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """Закрытие HTTP сессии"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_market_data(self) -> Dict:
        """Получение рыночных данных"""
        await self.init_session()
        
        try:
            async with self.session.get(FEAR_GREED_API, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    self.fear_greed_index = int(data['data'][0]['value'])
            
            async with self.session.get(f"{COINGECKO_API}/global", timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    self.btc_dominance = data['data']['market_cap_percentage']['btc']
            
            return {
                "fear_greed": self.fear_greed_index,
                "btc_dominance": self.btc_dominance
            }
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return {"fear_greed": 50, "btc_dominance": 50}
    
    async def get_ohlcv(self, symbol: str, interval: str = "1h", limit: int = 100) -> List:
        """Получение свечных данных"""
        await self.init_session()
        
        try:
            async with self.session.get(
                f"{BINANCE_API}/klines",
                params={"symbol": f"{symbol}USDT", "interval": interval, "limit": limit},
                timeout=10
            ) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            logger.error(f"Error getting OHLCV for {symbol}: {e}")
        
        return []
    
    async def get_24h_ticker(self, symbol: str) -> Dict:
        """Получение 24-часовой статистики"""
        await self.init_session()
        
        try:
            async with self.session.get(
                f"{BINANCE_API}/ticker/24hr",
                params={"symbol": f"{symbol}USDT"},
                timeout=10
            ) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            logger.error(f"Error getting ticker for {symbol}: {e}")
        
        return {}
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Расчет RSI"""
        if len(prices) < period + 1:
            return 50
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """Расчет EMA"""
        if not prices:
            return []
        
        ema = [prices[0]]
        multiplier = 2 / (period + 1)
        
        for i in range(1, len(prices)):
            ema.append((prices[i] - ema[-1]) * multiplier + ema[-1])
        
        return ema
    
    def calculate_macd(self, prices: List[float]) -> Tuple[float, float, float]:
        """Расчет MACD"""
        if len(prices) < 26:
            return 0, 0, 0
        
        ema_12 = self.calculate_ema(prices, 12)
        ema_26 = self.calculate_ema(prices, 26)
        
        macd_line = [ema_12[i] - ema_26[i] for i in range(len(prices))]
        signal_line = self.calculate_ema(macd_line, 9)
        
        return macd_line[-1], signal_line[-1], macd_line[-1] - signal_line[-1]
    
    def calculate_support_resistance(self, prices: List[float]) -> Tuple[float, float]:
        """Расчет уровней поддержки и сопротивления"""
        if not prices:
            return 0, 0
        
        recent_prices = prices[-20:]
        support = min(recent_prices)
        resistance = max(recent_prices)
        
        return support, resistance
    
    async def generate_trade_signal(self, symbol: str) -> Optional[TradeSignal]:
        """Генерация торгового сигнала"""
        try:
            ohlcv = await self.get_ohlcv(symbol)
            ticker = await self.get_24h_ticker(symbol)
            
            if not ohlcv or not ticker:
                return None
            
            prices = [float(candle[4]) for candle in ohlcv]
            volumes = [float(candle[5]) for candle in ohlcv]
            
            current_price = float(ticker['lastPrice'])
            volume_24h = float(ticker['quoteVolume'])
            
            if volume_24h < 1_000_000:
                return None
            
            # Технический анализ
            rsi = self.calculate_rsi(prices)
            macd, signal_line, histogram = self.calculate_macd(prices)
            ema_20 = self.calculate_ema(prices, 20)[-1]
            ema_50 = self.calculate_ema(prices, 50)[-1]
            support, resistance = self.calculate_support_resistance(prices)
            
            # Определение направления
            technical_score = 0
            
            # RSI анализ
            if rsi < 30:
                technical_score += 30  # Перепродан - сигнал на LONG
            elif rsi > 70:
                technical_score -= 30  # Перекуплен - сигнал на SHORT
            
            # MACD анализ
            if macd > signal_line and histogram > 0:
                technical_score += 20
            elif macd < signal_line and histogram < 0:
                technical_score -= 20
            
            # EMA анализ
            if ema_20 > ema_50 and current_price > ema_20:
                technical_score += 15
            elif ema_20 < ema_50 and current_price < ema_20:
                technical_score -= 15
            
            # Объемный анализ
            avg_volume = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else sum(volumes) / len(volumes)
            volume_change = (volumes[-1] - avg_volume) / avg_volume * 100 if avg_volume > 0 else 0
            
            if volume_change > 20:
                technical_score += 10
            elif volume_change < -20:
                technical_score -= 10
            
            # Рыночный контекст
            if self.fear_greed_index < 25:
                technical_score += 10  # Экстремальный страх - хорошее время для LONG
            elif self.fear_greed_index > 75:
                technical_score -= 10  # Экстремальная жадность - риск коррекции
            
            # Определение типа сигнала
            if technical_score > 10:
                signal_type = "LONG"
                confidence = min(abs(technical_score) + 50, 90)
            elif technical_score < -10:
                signal_type = "SHORT"
                confidence = min(abs(technical_score) + 50, 90)
            else:
                return None  # Нет четкого сигнала
            
            # Расчет уровней
            if signal_type == "LONG":
                entry_price = current_price
                stop_loss = support * 0.98  # 2% ниже поддержки
                take_profit = current_price * 1.05  # +5% от текущей цены
                potential_profit = 5.0
            else:  # SHORT
                entry_price = current_price
                stop_loss = resistance * 1.02  # 2% выше сопротивления
                take_profit = current_price * 0.95  # -5% от текущей цены
                potential_profit = 5.0
            
            # Расчет Risk/Reward
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # Фильтр по Risk/Reward
            if risk_reward_ratio < 1.5:
                return None
            
            signal = TradeSignal(
                symbol=symbol,
                name=CRYPTOCURRENCIES.get(symbol, symbol),
                signal_type=signal_type,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
                risk_reward_ratio=risk_reward_ratio,
                technical_score=technical_score,
                volume_24h=volume_24h,
                potential_profit=potential_profit
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error generating signal for {symbol}: {e}")
            return None
    
    async def generate_all_signals(self, limit: int = 10) -> List[TradeSignal]:
        """Генерация всех сигналов"""
        signals = []
        
        await self.get_market_data()
        
        symbols_to_analyze = list(CRYPTOCURRENCIES.keys())[:30]
        
        tasks = []
        for symbol in symbols_to_analyze:
            task = asyncio.create_task(self.generate_trade_signal(symbol))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, TradeSignal):
                signals.append(result)
        
        # Сортировка по уверенности и Risk/Reward
        signals.sort(key=lambda x: (x.confidence * x.risk_reward_ratio), reverse=True)
        
        return signals[:limit]

class TelegramBot:
    def __init__(self, token: str = BOT_TOKEN):
        self.token = token
        self.analyzer = CryptoAnalyzer()
        self.db = Database()
        self.application = None
        self.is_running = True
    
    def is_authorized(self, user_id: int) -> bool:
        """Проверка авторизации"""
        return user_id == OWNER_ID
    
    def format_signal(self, signal: TradeSignal) -> str:
        """Форматирование торгового сигнала"""
        if signal.signal_type == "LONG":
            emoji = "🟢"
            type_text = "LONG (Покупка)"
        else:
            emoji = "🔴"
            type_text = "SHORT (Продажа)"
        
        message = f"""
{emoji} СИГНАЛ: {type_text}

💰 {signal.name} ({signal.symbol})

━━━━━━━━━━━━━━━━━━━━━━
📊 Вход: ${signal.entry_price:,.4f}
🛑 Стоп-лосс: ${signal.stop_loss:,.4f}
✅ Тейк-профит: ${signal.take_profit:,.4f}
━━━━━━━━━━━━━━━━━━━━━━

📈 Потенциальная прибыль: {signal.potential_profit:.1f}%
⚖️ Risk/Reward: 1:{signal.risk_reward_ratio:.1f}
🎯 Уверенность: {signal.confidence:.1f}%

💵 Объем 24ч: ${signal.volume_24h:,.0f}
🌐 Fear & Greed: {self.analyzer.fear_greed_index}/100

⚠️ Всегда используйте стоп-лосс!
"""
        return message
    
    async def send_test_message(self):
        """Отправка тестового сообщения"""
        try:
            await self.application.bot.send_message(
                chat_id=OWNER_ID,
                text="✅ Бот запущен и готов к работе!\n\n"
                     "🎯 Отправьте /signals для получения торговых сигналов"
            )
        except Exception as e:
            logger.error(f"Error sending test message: {e}")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start"""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔️ Доступ запрещен!")
            return
        
        await update.message.reply_text(
            "👋 Добро пожаловать в Crypto Signals Bot!\n\n"
            "🎯 Я предоставляю торговые сигналы:\n"
            "• LONG (покупка) и SHORT (продажа)\n"
            "• Уровни входа, стоп-лосса и тейк-профита\n\n"
            "📋 Команды:\n"
            "/signals - Получить сигналы\n"
            "/long - Только LONG сигналы\n"
            "/short - Только SHORT сигналы\n"
            "/stats - Статистика\n"
            "/help - Помощь"
        )
    
    async def signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /signals"""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔️ Доступ запрещен!")
            return
        
        await update.message.reply_text("🔍 Анализирую рынок...")
        
        signals = await self.analyzer.generate_all_signals(10)
        
        if not signals:
            await update.message.reply_text("❌ Нет сигналов в данный момент")
            return
        
        longs = [s for s in signals if s.signal_type == "LONG"]
        shorts = [s for s in signals if s.signal_type == "SHORT"]
        
        message = "🎯 ТОРГОВЫЕ СИГНАЛЫ\n\n"
        
        if longs:
            message += "🟢 LONG СИГНАЛЫ:\n\n"
            for signal in longs[:5]:
                message += self.format_signal(signal)
                self.db.save_signal(signal)
                message += "\n"
        
        if shorts:
            message += "🔴 SHORT СИГНАЛЫ:\n\n"
            for signal in shorts[:5]:
                message += self.format_signal(signal)
                self.db.save_signal(signal)
                message += "\n"
        
        await update.message.reply_text(message)
    
    async def long_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /long"""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔️ Доступ запрещен!")
            return
        
        await update.message.reply_text("🔍 Ищу LONG сигналы...")
        
        signals = await self.analyzer.generate_all_signals(20)
        longs = [s for s in signals if s.signal_type == "LONG"]
        
        if not longs:
            await update.message.reply_text("❌ Нет LONG сигналов")
            return
        
        message = "🟢 LONG СИГНАЛЫ:\n\n"
        for signal in longs[:5]:
            message += self.format_signal(signal)
            self.db.save_signal(signal)
            message += "\n"
        
        await update.message.reply_text(message)
    
    async def short_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /short"""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔️ Доступ запрещен!")
            return
        
        await update.message.reply_text("🔍 Ищу SHORT сигналы...")
        
        signals = await self.analyzer.generate_all_signals(20)
        shorts = [s for s in signals if s.signal_type == "SHORT"]
        
        if not shorts:
            await update.message.reply_text("❌ Нет SHORT сигналов")
            return
        
        message = "🔴 SHORT СИГНАЛЫ:\n\n"
        for signal in shorts[:5]:
            message += self.format_signal(signal)
            self.db.save_signal(signal)
            message += "\n"
        
        await update.message.reply_text(message)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /stats"""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔️ Доступ запрещен!")
            return
        
        stats = self.db.get_stats()
        
        message = f"""
📊 СТАТИСТИКА СИГНАЛОВ

Всего сигналов: {stats['total']}
LONG: {stats['longs']}
SHORT: {stats['shorts']}
Средняя уверенность: {stats['avg_confidence']:.1f}%
"""
        await update.message.reply_text(message)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /help"""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔️ Доступ запрещен!")
            return
        
        help_text = """
🤖 CRYPTO SIGNALS BOT

📋 Команды:
/start - Запустить бота
/signals - Все сигналы
/long - Только LONG
/short - Только SHORT
/stats - Статистика
/help - Помощь

🎯 Что вы получаете:
• Направление (LONG/SHORT)
• Точку входа
• Стоп-лосс
• Тейк-профит
• Уровень уверенности
• Risk/Reward ratio

⚠️ Всегда используйте стоп-лосс!
"""
        await update.message.reply_text(help_text)
    
    async def run_auto_signals(self):
        """Автоматические сигналы каждые 4 часа"""
        logger.info("Starting auto signals...")
        
        await asyncio.sleep(10)
        
        while self.is_running:
            try:
                logger.info("Generating auto signals...")
                
                signals = await self.analyzer.generate_all_signals(5)
                
                if signals and self.application:
                    message = "🔔 АВТОМАТИЧЕСКИЕ СИГНАЛЫ\n\n"
                    
                    for signal in signals:
                        message += self.format_signal(signal)
                        self.db.save_signal(signal)
                        message += "\n"
                    
                    await self.application.bot.send_message(
                        chat_id=OWNER_ID,
                        text=message
                    )
                    logger.info("Auto signals sent!")
                
                await asyncio.sleep(4 * 60 * 60)
                
            except Exception as e:
                logger.error(f"Error in auto signals: {e}")
                await asyncio.sleep(60)
    
    async def run(self):
        """Запуск бота"""
        self.application = Application.builder().token(self.token).build()
        
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("signals", self.signals_command))
        self.application.add_handler(CommandHandler("long", self.long_command))
        self.application.add_handler(CommandHandler("short", self.short_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        logger.info("Bot started!")
        
        await self.send_test_message()
        
        asyncio.create_task(self.run_auto_signals())
        
        try:
            while True:
                await asyncio.sleep(1)
        finally:
            self.is_running = False
            await self.analyzer.close_session()
            await self.application.stop()

async def main():
    """Главная функция"""
    bot = TelegramBot(BOT_TOKEN)
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
