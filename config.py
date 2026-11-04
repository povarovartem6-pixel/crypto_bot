import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
CRYPTOBOT_API_TOKEN = os.getenv('CRYPTOBOT_API_TOKEN')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]

# Ссылки на поддержку и чат (заменишь на свои)
SUPPORT_LINK = "https://t.me/your_support_bot"
CHAT_LINK = "https://t.me/your_chat"

TARIFFS = {
    'free':  {'name': 'Free',  'price': 0,  'coins_limit': 2,   'timeframes': ['15м', '1ч'], 'signals_per_day': 3},
    'pro':   {'name': 'PRO',   'price': 30, 'coins_limit': 999, 'timeframes': ['5м', '15м', '1ч', '4ч', '1д'], 'signals_per_day': 999},
}

COINS = {
    'top20': ['BTC','ETH','BNB','SOL','XRP','ADA','DOGE','AVAX','DOT','LINK',
              'MATIC','UNI','ATOM','LTC','BCH','NEAR','ALGO','VET','ICP','FIL'],
    'defi':  ['AAVE','COMP','MKR','SNX','CRV','SUSHI','CAKE','1INCH','BAL','YFI','LDO','GMX','DYDX'],
    'l1l2':  ['APT','ARB','OP','SUI','SEI','TIA','INJ','TON','TRX','EGLD','HBAR','FTM'],
    'meme':  ['SHIB','PEPE','FLOKI','BONK','WIF'],
    'ai':    ['GRT','OCEAN','FET','AGIX','RNDR','THETA','AR'],
}
ALL_COINS = sorted(set(sum(COINS.values(), [])))

FUTURES_CONFIG = {'max_leverage': 10, 'min_leverage': 1, 'risk_per_trade': 0.01}

LEGAL_DISCLAIMER = """
📄 <b>ПРАВИЛА ПОЛЬЗОВАНИЯ И ОТКАЗ ОТ ОТВЕТСТВЕННОСТИ</b>

Бот ShiperSignal - аналитический инструмент. Бот <b>не является</b> финансовым советником.
Торговля фьючерсами связана с высоким риском. Бот <b>не гарантирует прибыль</b>.
Оплата производится в USDT через CryptoBot. Это не инвестиция.

<i>Нажимая «Согласен», вы принимаете все риски.</i>
"""

LESSONS = {
    "lvl1_1": {"title": "🛑 Стоп-лосс", "text": "<b>Урок 1: Стоп-лосс</b>\n\nЭто ваша страховка. Если цена идет против вас, стоп закроет сделку с минимальным убытком (1-2%), а не сольет весь депозит."},
    "lvl1_2": {"title": "💰 Правило 1%", "text": "<b>Урок 2: Риск-менеджмент</b>\n\nНикогда не рискуйте больше 1% от депозита в одной сделке. Если у вас $1000, максимальный убыток — $10."},
    "lvl2_1": {"title": "📊 Что такое RSI", "text": "<b>Урок 3: Индикатор RSI</b>\n\nПоказывает перекупленность (выше 70) или перепроданность (ниже 30). Бот не покупает, если рынок перегрет."},
    "lvl2_2": {"title": "📈 Что такое Плечо", "text": "<b>Урок 4: Плечо на фьючерсах</b>\n\nПлечо увеличивает и прибыль, и убыток. Чем выше плечо, тем ближе ликвидация. Бот всегда пишет безопасное плечо."},
    "lvl3_1": {"title": "🎯 Фиксация профита", "text": "<b>Урок 5: TP1 и TP2</b>\n\nКогда цена достигает TP1, закройте половину позиции и переведите стоп в безубыток."},
}
