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

# Список криптовалют (сокращенный для скорости)
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
class Prediction:
    symbol: str
    name: str
    current_price: float
    predicted_price: float
    change_percent: float
    confidence: float
    direction: str
    timeframe: str = "24h"
    technical_score: float = 0
    onchain_score: float = 0
    market_score: float = 0
    volume_24h: float = 0
    liquidity_score: float = 0

class Database:
    def __init__(self, db_path: str = "crypto_predictions.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    predicted_price REAL NOT NULL,
                    actual_price REAL,
                    change_percent REAL NOT NULL,
                    confidence REAL NOT NULL,
                    direction TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    resolved_at TIMESTAMP,
                    is_correct BOOLEAN,
                    technical_score REAL,
                    onchain_score REAL,
                    market_score REAL
                )
            ''')
            
            conn.commit()
    
    def save_prediction(self, prediction: Prediction):
        """Сохранение прогноза"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO predictions 
                (symbol, predicted_price, change_percent, confidence, direction, 
                 created_at, technical_score, onchain_score, market_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                prediction.symbol,
                prediction.predicted_price,
                prediction.change_percent,
                prediction.confidence,
                prediction.direction,
                datetime.now().isoformat(),
                prediction.technical_score,
                prediction.onchain_score,
                prediction.market_score
            ))
            conn.commit()
    
    def get_stats(self) -> Dict:
        """Получение статистики"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct,
                    AVG(confidence) as avg_conf
                FROM predictions 
                WHERE is_correct IS NOT NULL
            ''')
            result = cursor.fetchone()
            
            return {
                "total": result[0] or 0,
                "correct": result[1] or 0,
                "accuracy": (result[1] / result[0] * 100) if result[0] > 0 else 0,
                "avg_confidence": result[2] or 0
            }

class CryptoAnalyzer:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.fear_greed_index = 50
        self.btc_dominance = 50
        self.analysis_cache = {}
    
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
            # Получение Fear & Greed Index
            async with self.session.get(FEAR_GREED_API) as response:
                if response.status == 200:
                    data = await response.json()
                    self.fear_greed_index = int(data['data'][0]['value'])
            
            # Получение доминации BTC
            async with self.session.get(f"{COINGECKO_API}/global") as response:
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
        """Получение свечных данных с Binance"""
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
    
    def calculate_bollinger_bands(self, prices: List[float], period: int = 20) -> Tuple[float, float, float]:
        """Расчет полос Боллинджера"""
        if len(prices) < period:
            return prices[-1], prices[-1] * 1.02, prices[-1] * 0.98
        
        recent_prices = prices[-period:]
        sma = sum(recent_prices) / period
        
        variance = sum([(x - sma) ** 2 for x in recent_prices]) / period
        std_dev = variance ** 0.5
        
        upper_band = sma + (std_dev * 2)
        lower_band = sma - (std_dev * 2)
        
        return upper_band, sma, lower_band
    
    async def analyze_crypto(self, symbol: str) -> Optional[Prediction]:
        """Комплексный анализ криптовалюты"""
        try:
            # Получение данных
            ohlcv = await self.get_ohlcv(symbol)
            ticker = await self.get_24h_ticker(symbol)
            
            if not ohlcv or not ticker:
                return None
            
            # Извлечение цен
            prices = [float(candle[4]) for candle in ohlcv]
            volumes = [float(candle[5]) for candle in ohlcv]
            
            current_price = float(ticker['lastPrice'])
            volume_24h = float(ticker['quoteVolume'])
            
            # Проверка ликвидности (снижен порог для большего количества сигналов)
            if volume_24h < 1_000_000:  # Минимальный объем $1M
                return None
            
            # Технический анализ
            rsi = self.calculate_rsi(prices)
            macd, signal, histogram = self.calculate_macd(prices)
            upper_bb, middle_bb, lower_bb = self.calculate_bollinger_bands(prices)
            
            # EMA
            ema_20 = self.calculate_ema(prices, 20)[-1]
            ema_50 = self.calculate_ema(prices, 50)[-1]
            
            # Технический скоринг
            technical_score = 0
            
            # RSI анализ (более агрессивный)
            if rsi < 35:
                technical_score += 25
            elif rsi > 65:
                technical_score -= 25
            
            # MACD анализ
            if macd > signal:
                technical_score += 20
            elif macd < signal:
                technical_score -= 20
            
            # EMA анализ
            if ema_20 > ema_50:
                technical_score += 15
            elif ema_20 < ema_50:
                technical_score -= 15
            
            # Bollinger Bands
            if current_price < lower_bb:
                technical_score += 10
            elif current_price > upper_bb:
                technical_score -= 10
            
            # Объемный анализ
            avg_volume = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else sum(volumes) / len(volumes)
            volume_change = (volumes[-1] - avg_volume) / avg_volume * 100 if avg_volume > 0 else 0
            
            if volume_change > 30:
                technical_score += 15
            elif volume_change < -30:
                technical_score -= 15
            
            # Рыночный анализ
            market_score = 0
            
            if self.fear_greed_index < 30:
                market_score += 10
            elif self.fear_greed_index > 70:
                market_score -= 10
            
            # Общий скоринг
            total_score = technical_score * 0.8 + market_score * 0.2
            
            # Определение направления и уверенности
            direction = "up" if total_score > 0 else "down"
            confidence = min(abs(total_score) + 50, 90)  # Базовый уровень 50% + скор
            
            # Прогнозируемое изменение
            base_change = abs(total_score) / 3
            predicted_change = min(max(base_change, 2), 10)
            
            if direction == "down":
                predicted_change = -predicted_change
            
            predicted_price = current_price * (1 + predicted_change / 100)
            
            prediction = Prediction(
                symbol=symbol,
                name=CRYPTOCURRENCIES.get(symbol, symbol),
                current_price=current_price,
                predicted_price=predicted_price,
                change_percent=predicted_change,
                confidence=confidence,
                direction=direction,
                technical_score=technical_score,
                onchain_score=volume_change,
                market_score=market_score,
                volume_24h=volume_24h,
                liquidity_score=min(volume_24h / 100_000_000 * 100, 100)
            )
            
            return prediction
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return None
    
    async def analyze_top_cryptos(self, limit: int = 10) -> List[Prediction]:
        """Анализ топ криптовалют"""
        predictions = []
        
        # Получение рыночных данных
        await self.get_market_data()
        
        # Анализ основных криптовалют
        symbols_to_analyze = list(CRYPTOCURRENCIES.keys())[:30]  # Анализируем топ-30
        
        tasks = []
        for symbol in symbols_to_analyze:
            task = asyncio.create_task(self.analyze_crypto(symbol))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Prediction):
                predictions.append(result)
        
        # Сортировка по уверенности
        predictions.sort(key=lambda x: x.confidence, reverse=True)
        
        return predictions[:limit]

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
    
    def format_prediction(self, prediction: Prediction) -> str:
        """Форматирование прогноза"""
        direction_emoji = "📈" if prediction.direction == "up" else "📉"
        direction_text = "РОСТ" if prediction.direction == "up" else "ПАДЕНИЕ"
        
        message = f"""
🔮 ПРОГНОЗ НА 24 ЧАСА

{direction_emoji} {prediction.name} ({prediction.symbol})

📊 Направление: {direction_text}
💰 Текущая цена: ${prediction.current_price:,.4f}
🎯 Прогноз: ${prediction.predicted_price:,.4f}
📈 Изменение: {prediction.change_percent:+.2f}%

🎯 Уверенность: {prediction.confidence:.1f}%

📊 Объем 24ч: ${prediction.volume_24h:,.0f}
🌐 Fear & Greed: {self.analyzer.fear_greed_index}/100

⚠️ Не является финансовой рекомендацией!
"""
        return message
    
    async def send_test_message(self):
        """Отправка тестового сообщения"""
        try:
            await self.application.bot.send_message(
                chat_id=OWNER_ID,
                text="✅ Бот запущен и готов к работе!\n\n"
                     "Начинаю анализ рынка..."
            )
        except Exception as e:
            logger.error(f"Error sending test message: {e}")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start"""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔️ Доступ запрещен!")
            return
        
        await update.message.reply_text(
            "👋 Добро пожаловать в Crypto Predictor Bot!\n\n"
            "🔍 Начинаю анализ рынка...\n\n"
            "Доступные команды:\n"
            "/predict <SYMBOL> - Прогноз по конкретной монете\n"
            "/top10 - Топ-10 лучших прогнозов\n"
            "/signals - Получить сигналы\n"
            "/stats - Статистика точности\n"
            "/help - Помощь"
        )
        
        # Сразу запускаем анализ
        await self.send_signals(update)
    
    async def predict_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /predict"""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔️ Доступ запрещен!")
            return
        
        if not context.args:
            await update.message.reply_text("⚠️ Укажите символ, например: /predict BTC")
            return
        
        symbol = context.args[0].upper()
        if symbol not in CRYPTOCURRENCIES:
            await update.message.reply_text(f"❌ Криптовалюта {symbol} не найдена")
            return
        
        await update.message.reply_text(f"🔍 Анализирую {symbol}...")
        
        prediction = await self.analyzer.analyze_crypto(symbol)
        
        if prediction:
            formatted = self.format_prediction(prediction)
            self.db.save_prediction(prediction)
            await update.message.reply_text(formatted)
        else:
            await update.message.reply_text(f"❌ Не удалось получить прогноз для {symbol}")
    
    async def top10_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /top10"""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔️ Доступ запрещен!")
            return
        
        await self.send_signals(update)
    
    async def signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /signals"""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔️ Доступ запрещен!")
            return
        
        await self.send_signals(update)
    
    async def send_signals(self, update: Update = None):
        """Отправка сигналов"""
        try:
            await update.message.reply_text("🔍 Анализирую рынок... Это может занять несколько секунд.")
            
            predictions = await self.analyzer.analyze_top_cryptos(10)
            
            if not predictions:
                await update.message.reply_text("❌ Не удалось получить прогнозы")
                return
            
            message = "🏆 ТОП-10 ПРОГНОЗОВ НА 24 ЧАСА\n\n"
            
            for i, pred in enumerate(predictions, 1):
                emoji = "📈" if pred.direction == "up" else "📉"
                message += f"{i}. {emoji} {pred.name} ({pred.symbol})\n"
                message += f"   Цена: ${pred.current_price:,.4f}\n"
                message += f"   Изменение: {pred.change_percent:+.2f}%\n"
                message += f"   Уверенность: {pred.confidence:.1f}%\n\n"
                
                # Сохраняем прогноз
                self.db.save_prediction(pred)
            
            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Error sending signals: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /stats"""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔️ Доступ запрещен!")
            return
        
        stats = self.db.get_stats()
        
        message = f"""
📊 СТАТИСТИКА ПРОГНОЗОВ

Всего прогнозов: {stats['total']}
Верных: {stats['correct']}
Точность: {stats['accuracy']:.1f}%
Средняя уверенность: {stats['avg_confidence']:.1f}%
"""
        await update.message.reply_text(message)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /help"""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔️ Доступ запрещен!")
            return
        
        help_text = """
🤖 CRYPTO PREDICTOR BOT

📋 Команды:
/start - Запустить бота
/predict <SYMBOL> - Прогноз по конкретной монете
/top10 - Топ-10 лучших прогнозов
/signals - Получить сигналы
/stats - Статистика точности
/help - Это сообщение

📊 Анализируемые данные:
• Технический анализ (RSI, MACD, EMA)
• Объемы торгов
• Рыночные индикаторы
• Fear & Greed Index

⚠️ Бот не предоставляет финансовые рекомендации!
"""
        await update.message.reply_text(help_text)
    
    async def run_auto_predictions(self):
        """Автоматические прогнозы каждые 4 часа"""
        logger.info("Starting auto predictions...")
        
        # Ждем 10 секунд после запуска
        await asyncio.sleep(10)
        
        while self.is_running:
            try:
                logger.info("Running auto predictions...")
                
                predictions = await self.analyzer.analyze_top_cryptos(5)
                
                if predictions and self.application:
                    message = "🔔 АВТО-ПРОГНОЗЫ НА 24 ЧАСА\n\n"
                    
                    for pred in predictions[:5]:
                        emoji = "📈" if pred.direction == "up" else "📉"
                        message += f"{emoji} {pred.name}: {pred.change_percent:+.2f}% "
                        message += f"(уверенность: {pred.confidence:.1f}%)\n"
                        message += f"Цена: ${pred.current_price:,.4f}\n\n"
                        
                        # Сохраняем прогноз
                        self.db.save_prediction(pred)
                    
                    await self.application.bot.send_message(
                        chat_id=OWNER_ID,
                        text=message
                    )
                    logger.info("Auto predictions sent!")
                
                # Ждем 4 часа
                await asyncio.sleep(4 * 60 * 60)
                
            except Exception as e:
                logger.error(f"Error in auto predictions: {e}")
                await asyncio.sleep(60)
    
    async def run(self):
        """Запуск бота"""
        # Инициализация приложения
        self.application = Application.builder().token(self.token).build()
        
        # Регистрация обработчиков
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("predict", self.predict_command))
        self.application.add_handler(CommandHandler("top10", self.top10_command))
        self.application.add_handler(CommandHandler("signals", self.signals_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        # Запуск бота
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        logger.info("Bot started!")
        
        # Отправка тестового сообщения
        await self.send_test_message()
        
        # Запуск авто-прогнозов
        asyncio.create_task(self.run_auto_predictions())
        
        try:
            # Держим бота запущенным
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
