from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_IDS, LESSONS

def get_reply_main_menu(user_id=None, trial_used=1):
    kb = [
        [KeyboardButton("📊 Сигналы"), KeyboardButton("🟢 Мои сделки")],
        [KeyboardButton("🌅 Дайджест"), KeyboardButton("🎓 Обучение")],
        [KeyboardButton("💎 Тарифы"), KeyboardButton("👤 Профиль")],
        [KeyboardButton("💬 Чат трейдеров"), KeyboardButton("🆘 Поддержка")],
    ]
    if trial_used == 0:
        kb.insert(0, [KeyboardButton("🎁 Пробный PRO (3 дня)")])
        
    if user_id in ADMIN_IDS:
        kb.append([KeyboardButton("👑 Админ-панель")])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True, is_persistent=True)

def get_profile_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Изменить депозит", callback_data='change_deposit')],
        [InlineKeyboardButton("📜 История сделок", callback_data='trade_history')],
        [InlineKeyboardButton("🏦 Сменить биржу", callback_data='change_exch')]
    ])

def get_signal_actions_kb(signal_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Взять в работу", callback_data=f'take_{signal_id}'), InlineKeyboardButton("❌ Пропустить", callback_data=f'skip_{signal_id}')]
    ])

def get_exchange_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟡 Binance", callback_data='exch_binance'), InlineKeyboardButton("🟠 Bybit", callback_data='exch_bybit')],
        [InlineKeyboardButton("⚫️ OKX", callback_data='exch_okx'), InlineKeyboardButton("🔵 BingX", callback_data='exch_bingx')],
        [InlineKeyboardButton("🟣 Bitget", callback_data='exch_bitget'), InlineKeyboardButton("🟢 KuCoin", callback_data='exch_kucoinfutures')],
    ])

def get_onboarding_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Я ознакомился", callback_data='onboard_read')]])

def get_legal_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Я согласен с правилами", callback_data='legal_accept')]])

def payment_kb(pay_url, invoice_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Перейти к оплате", url=pay_url)],
        [InlineKeyboardButton("✅ Я оплатил", callback_data=f'check_{invoice_id}')]
    ])

def tariffs_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 PRO - $10/неделя", callback_data='tariff_pro_week')],
        [InlineKeyboardButton("💎 PRO - $30/месяц", callback_data='tariff_pro_month')]
    ])

def get_lessons_levels_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Уровень 1: База", callback_data='level_lvl1')],
        [InlineKeyboardButton("🟡 Уровень 2: Индикаторы", callback_data='level_lvl2')],
        [InlineKeyboardButton("🔴 Уровень 3: Практика", callback_data='level_lvl3')],
        [InlineKeyboardButton("🔙 В главное меню", callback_data='main_menu')]
    ])

def get_level_lessons_kb(level_prefix, user_lessons_done: list):
    kb = []
    for key, lesson in LESSONS.items():
        if key.startswith(level_prefix):
            title = lesson['title'].split(': ')[-1]
            status = "✅ " if key in user_lessons_done else ""
            kb.append([InlineKeyboardButton(f"{status}{title}", callback_data=f'lesson_{key}')])
    
    kb.append([InlineKeyboardButton("🔙 Назад к уровням", callback_data='lessons_menu')])
    return InlineKeyboardMarkup(kb)

def get_lesson_back_kb(level_prefix):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад к урокам", callback_data=f'level_{level_prefix}')]
    ])

def get_admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Последние 50 юзеров", callback_data='admin_last_50')],
        [InlineKeyboardButton("💎 Только оплатившие", callback_data='admin_only_paid')],
        [InlineKeyboardButton("🎁 Выдать PRO по ID", callback_data='admin_give_pro')],
        [InlineKeyboardButton("📢 Сделать рассылку", callback_data='admin_broadcast')],
    ])

def get_admin_give_pro_kb(target_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Выдать на 7 дней", callback_data=f'give_pro_7_{target_id}')],
        [InlineKeyboardButton("📅 Выдать на 30 дней", callback_data=f'give_pro_30_{target_id}')]
    ])
