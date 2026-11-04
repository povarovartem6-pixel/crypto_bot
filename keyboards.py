from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_IDS, LESSONS

def get_reply_main_menu(user_id=None):
    kb = [
        [KeyboardButton("📊 Сигналы"), KeyboardButton("💼 Мой профит")],
        [KeyboardButton("🎓 Обучение"), KeyboardButton("💎 Тарифы")],
        [KeyboardButton("👤 Профиль"), KeyboardButton("💬 Чат трейдеров")],
        [KeyboardButton("🆘 Поддержка")],
    ]
    if user_id in ADMIN_IDS:
        kb.append([KeyboardButton("👑 Админ-панель")])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True, is_persistent=True)

def get_profile_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏦 Сменить биржу", callback_data='change_exch')],
        [InlineKeyboardButton("📜 История сделок", callback_data='trade_history')]
    ])

def get_onboarding_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Я ознакомился", callback_data='onboard_read')]])

def get_legal_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Я согласен с правилами", callback_data='legal_accept')]])

def get_exchange_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟡 Binance", callback_data='exch_binance'), InlineKeyboardButton("🟠 Bybit", callback_data='exch_bybit')],
        [InlineKeyboardButton("⚫️ OKX", callback_data='exch_okx'), InlineKeyboardButton("🔵 BingX", callback_data='exch_bingx')],
        [InlineKeyboardButton("🟣 Bitget", callback_data='exch_bitget'), InlineKeyboardButton("🟢 KuCoin", callback_data='exch_kucoinfutures')],
    ])

def get_signal_actions_kb(signal_id, coin, exchange_name='binance'):
    urls = {
        'binance': f"https://www.binance.com/ru/futures/{coin}USDT",
        'bybit': f"https://www.bybit.com/trade/usdt/{coin}USDT",
        'okx': f"https://www.okx.com/trade-swap/{coin}-usdt-swap",
        'bingx': f"https://bingx.com/ru-ru/perpetual/{coin}-USDT/",
        'bitget': f"https://www.bitget.com/futures/usdt/{coin}USDT",
        'kucoinfutures': f"https://www.kucoin.com/trade/futures/{coin}USDT",
    }
    url = urls.get(exchange_name, urls['binance'])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Взять в работу", callback_data=f'take_{signal_id}'), InlineKeyboardButton("❌ Пропустить", callback_data=f'skip_{signal_id}')],
        [InlineKeyboardButton(f"📈 Открыть на {exchange_name.capitalize()}", url=url)]
    ])

def payment_kb(pay_url, invoice_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Перейти к оплате", url=pay_url)],
        [InlineKeyboardButton("✅ Я оплатил", callback_data=f'check_{invoice_id}')]
    ])

def tariffs_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 PRO - $30/мес", callback_data='tariff_pro')],
    ])

# === КРАСИВОЕ МЕНЮ ОБУЧЕНИЯ ===

def get_lessons_levels_kb():
    """Главное меню обучения (выбор уровней)"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Уровень 1: База", callback_data='level_lvl1')],
        [InlineKeyboardButton("🟡 Уровень 2: Индикаторы", callback_data='level_lvl2')],
        [InlineKeyboardButton("🔴 Уровень 3: Практика", callback_data='level_lvl3')],
        [InlineKeyboardButton("🔙 В главное меню", callback_data='main_menu')]
    ])

def get_level_lessons_kb(level_prefix, user_lessons_done: list):
    """Уроки внутри выбранного уровня (с галочками прогресса)"""
    kb = []
    for key, lesson in LESSONS.items():
        if key.startswith(level_prefix):
            # Убираем "Уровень X: " из названия, чтобы кнопка была компактной
            title = lesson['title'].split(': ')[-1]
            status = "✅ " if key in user_lessons_done else ""
            kb.append([InlineKeyboardButton(f"{status}{title}", callback_data=f'lesson_{key}')])
    
    # Кнопка возврата к списку уровней
    kb.append([InlineKeyboardButton("🔙 Назад к уровням", callback_data='lessons_menu')])
    return InlineKeyboardMarkup(kb)

def get_lesson_back_kb(level_prefix):
    """Кнопка возврата из самого текста урока"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад к урокам", callback_data=f'level_{level_prefix}')]
    ])
