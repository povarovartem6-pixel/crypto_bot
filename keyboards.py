from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_IDS

def get_reply_main_menu(user_id=None):
    kb = [
        [KeyboardButton("📊 Сигналы"), KeyboardButton("💼 Мой профит")],
        [KeyboardButton("🎓 Обучение"), KeyboardButton("💎 Тарифы")],
        [KeyboardButton("👤 Профиль"), KeyboardButton("⚙️ Настройки")],
    ]
    if user_id in ADMIN_IDS:
        kb.append([KeyboardButton("👑 Админ-панель")])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True, is_persistent=True)

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
        [InlineKeyboardButton("✅ Взять в работу", callback_data=f'confirm_take_{signal_id}'), InlineKeyboardButton("❌ Пропустить", callback_data=f'skip_{signal_id}')],
        [InlineKeyboardButton("💰 Указать свою сумму", callback_data=f'custom_size_{signal_id}')],
        [InlineKeyboardButton(f"📈 Открыть на {exchange_name.capitalize()}", url=url)]
    ])

def get_confirm_take_kb(signal_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Да, открыть сделку", callback_data=f'take_{signal_id}')],
        [InlineKeyboardButton("🔙 Нет, отмена", callback_data=f'cancel_take_{signal_id}')]
    ])

def payment_kb(pay_url, invoice_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Перейти к оплате", url=pay_url)],
        [InlineKeyboardButton("✅ Я оплатил", callback_data=f'check_{invoice_id}')]
    ])

def tariffs_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆓 Free", callback_data='tariff_free')],
        [InlineKeyboardButton("🔥 PRO - $30/мес", callback_data='tariff_pro')],
    ])
