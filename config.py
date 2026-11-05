import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
CRYPTOBOT_API_TOKEN = os.getenv('CRYPTOBOT_API_TOKEN')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]

SUPPORT_LINK = "https://t.me/shipersupportbot"
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

TAKER_FEE = 0.001
SLIPPAGE = 0.0005
MIN_RR = 1.8
MIN_EDGE = 0.003
RISK_PER_TRADE = 0.01

LEGAL_DISCLAIMER = """
📄 <b>ПРАВИЛА ПОЛЬЗОВАНИЯ И ОТКАЗ ОТ ОТВЕТСТВЕННОСТИ</b>

Бот ShiperSignal - аналитический инструмент. Бот <b>не является</b> финансовым советником.
Торговля фьючерсами связана с высоким риском. Бот <b>не гарантирует прибыль</b>.
Оплата производится в USDT через CryptoBot. Это не инвестиция.

<i>Нажимая «Согласен», вы принимаете все риски.</i>
"""

LESSONS = {
    "lvl1_1": {"title": "Уровень 1: Стоп-лосс", "text": "<b>🛑 Урок 1: Стоп-лосс</b>\n\nЭто ваша страховка. Если цена идет против вас, стоп закроет сделку с минимальным убытком (1-2%), а не сольет весь депозит.\n\nВ нашем боте стоп-лосс <b>уже встроен</b> в каждый сигнал."},
    "lvl1_2": {"title": "Уровень 1: Правило 1%", "text": "<b>💰 Урок 2: Риск-менеджмент</b>\n\nНикогда не рискуйте больше 1% от депозита в одной сделке. \n\nЕсли у вас $1000, максимальный убыток — $10. Бот автоматически считает размер позиции по этому правилу."},
    "lvl2_1": {"title": "Уровень 2: Что такое RSI", "text": "<b>📊 Урок 3: Индикатор RSI</b>\n\nRSI показывает, перекуплена монета или перепродана.\n• Выше 70 — перекуплена (скоро может упасть).\n• Ниже 30 — перепродана (скоро может вырасти).\n\nБот не покупает, если RSI уже 80."},
    "lvl2_2": {"title": "Уровень 2: Что такое Плечо", "text": "<b>📈 Урок 4: Плечо на фьючерсах</b>\n\nПлечо увеличивает и прибыль, и убыток. Чем выше плечо, тем ближе ликвидация.\n\nБот всегда пишет безопасное плечо в сигнале. Не ставьте больше!"},
    "lvl3_1": {"title": "Уровень 3: Фиксация профита", "text": "<b>🎯 Урок 5: TP1 и TP2</b>\n\nКогда цена достигает TP1, закройте половину позиции и переведите стоп в безубыток (на цену входа). Остаток ведем до TP2."},
}
