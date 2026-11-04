import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
CRYPTOBOT_API_TOKEN = os.getenv('CRYPTOBOT_API_TOKEN')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]

TARIFFS = {
    'free':  {'name': 'Free',  'price': 0,  'coins_limit': 2,   'timeframes': ['15м', '1ч'], 'delay': 0, 'signals_per_day': 3},
    'pro':   {'name': 'PRO',   'price': 30, 'coins_limit': 999, 'timeframes': ['5м', '15м', '1ч', '4ч', '1д'], 'delay': 0, 'signals_per_day': 999},
    'vip':   {'name': 'VIP',   'price': 50, 'coins_limit': 999, 'timeframes': ['5м', '15м', '1ч', '4ч', '1д'], 'delay': 0, 'signals_per_day': 999},
}

COINS = {
    'top20': ['BTC','ETH','BNB','SOL','XRP','ADA','DOGE','AVAX','DOT','LINK',
              'MATIC','UNI','ATOM','LTC','BCH','NEAR','ALGO','VET','ICP','FIL'],
    'defi':  ['AAVE','COMP','MKR','SNX','CRV','SUSHI','CAKE','1INCH','BAL','YFI','LDO','GMX','DYDX'],
    'l1l2':  ['APT','ARB','OP','SUI','SEI','TIA','INJ','TON','TRX','EGLD','HBAR','FTM'],
    'meme':  ['SHIB','PEPE','FLOKI','BONK','WIF'],
    'ai':    ['GRT','OCEAN','FET','AGIX','RNDR','THETA','AR'],
    'gaming':['SAND','MANA','AXS','GALA','ENJ','ILV','MAGIC'],
    'infra': ['LINK','BAND','API3','TRB','PYTH'],
}
ALL_COINS = sorted(set(sum(COINS.values(), [])))

TRIAL_PERIOD_DAYS = 3
TRIAL_TARIFF = 'pro'

# ВОТ ЭТИ ПЕРЕМЕННЫЕ НУЖНО ДОБАВИТЬ:
TAKER_FEE = 0.001
SLIPPAGE = 0.0005
MIN_RR = 1.8
MIN_EDGE = 0.003
RISK_PER_TRADE = 0.01

FUTURES_CONFIG = {
    'max_leverage': 10,
    'min_leverage': 1,
    'default_leverage': 3,
    'risk_per_trade': 0.01,
}

LEGAL_DISCLAIMER = """
📄 <b>ПРАВИЛА ПОЛЬЗОВАНИЯ И ОТКАЗ ОТ ОТВЕТСТВЕННОСТИ</b>

<b>1. ОБЩИЕ ПОЛОЖЕНИЯ</b>
Бот ShiperSignal - аналитический инструмент, предоставляющий информацию о точках входа на рынке. Бот <b>не является</b> финансовым советником или брокером.

<b>2. ОТСУТСТВИЕ ГАРАНТИЙ</b>
Торговля фьючерсами связана с высоким риском. Бот <b>не гарантирует прибыль</b>. Вы принимаете все торговые решения самостоятельно и несёте полную ответственность за свои средства.

<b>3. ОПЛАТА И ПОДПИСКА</b>
Оплата производится в USDT через сервис CryptoBot за доступ к функционалу бота. Это не инвестиция.

<b>4. ОГРАНИЧЕНИЕ ОТВЕТСТВЕННОСТИ</b>
Разработчик не несёт ответственности за убытки, возникшие в результате использования бота. Telegram не является стороной сделки.

<i>Нажимая «Согласен», вы подтверждаете, что ознакомились с правилами и принимаете все риски.</i>
"""
