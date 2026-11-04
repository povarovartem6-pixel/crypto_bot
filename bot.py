import asyncio, logging, json
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from config import *
from database import Database, get_conn
from signals import SignalGenerator
from keyboards import (
    get_reply_main_menu, get_onboarding_kb, get_legal_kb, get_exchange_kb,
    get_signal_actions_kb, get_confirm_take_kb, payment_kb, tariffs_kb
)
from tracker import TradeTracker, PaperTrader
from chart_generator import generate_signal_chart
from payments import CryptoBotPayment

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
db = Database()
sig_gen = SignalGenerator(db)
tracker = TradeTracker(db)
paper = PaperTrader(db)
payment = CryptoBotPayment()


# === СТАРТ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.add_user(u.id, u.username or '', u.first_name or '', u.last_name or '')
    user = db.get_user(u.id)

    # Онбординг
    if not context.user_data.get('onboard_done'):
        instruction = f"""
👋 <b>Добро пожаловать в ShiperSignal, {u.first_name}!</b>

Перед началом работы, пожалуйста, ознакомьтесь с инструкцией:

1️⃣ <b>Бот работает на ФЬЮЧЕРСАХ.</b> Плечо подбирается автоматически. Не ставьте больше, чем советует бот - это риск ликвидации.

2️⃣ <b>Как брать сигнал?</b> Нажмите кнопку <b>✅ «Взять в работу»</b>. Бот будет сопровождать сделку.

3️⃣ <b>Риск-менеджмент.</b> Всегда ставьте стоп-лосс и не рискуйте больше 1% от депозита.

4️⃣ <b>Бесплатная версия (Free).</b> 3 сигнала в день по BTC и ETH. Для доступа к 80+ монетам оформите PRO.

⚠️ <i>Бот не гарантирует прибыль. Это инструмент аналитики.</i>
"""
        await update.message.reply_text(instruction, reply_markup=get_onboarding_kb(), parse_mode='HTML')
        return

    # Баланс
    if user['balance_usdt'] == 0:
        context.user_data['awaiting_deposit'] = True
        await update.message.reply_text("💰 Укажите ваш стартовый виртуальный депозит (например, <code>1000</code>):", parse_mode='HTML')
        return

    await update.message.reply_text(
        f"👋 С возвращением, {user['first_name']}!\nВыберите действие 👇",
        reply_markup=get_reply_main_menu(u.id)
    )


# === СИГНАЛЫ ===
async def top_signals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = db.get_user(update.effective_user.id)

    if u['tariff'] == 'free':
        today = datetime.now().date().isoformat()
        if context.user_data.get('last_signal_date') == today and context.user_data.get('signals_today', 0) >= 3:
            await update.message.reply_text("🛑 <b>Лимит (3/3) исчерпан.</b>\n\nОформите PRO для доступа к 80+ монетам.", parse_mode='HTML')
            return
        context.user_data['last_signal_date'] = today
        context.user_data['signals_today'] = context.user_data.get('signals_today', 0) + 1

    coins = ['BTC', 'ETH'] if u['tariff'] == 'free' else ALL_COINS[:15]
    await update.message.reply_text("⏳ Сканирую рынок...")

    sigs = sig_gen.scan(coins, TARIFFS[u['tariff']]['timeframes'][0])
    if not sigs:
        await update.message.reply_text("😴 Нет идеальных сетапов. Рынок шумит.")
        return

    s = sigs[0]
    text = sig_gen.format(s, user_balance=u.get('balance_usdt', 1000), exchange_name=u.get('exchange', 'binance'))
    kb = get_signal_actions_kb(s['id'], s['coin'], u.get('exchange', 'binance'))

    try:
        chart = generate_signal_chart(s['coin'], s['signal_type'], s['entry_price'], s['stop_loss'], s['target_prices'][0])
    except Exception:
        chart = None

    if chart:
        await update.message.reply_photo(photo=chart, caption=text, reply_markup=kb, parse_mode='HTML')
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode='HTML')


# === CALLBACKS ===
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    u = db.get_user(user_id)

    if q.data == 'onboard_read':
        await q.edit_message_text(LEGAL_DISCLAIMER, reply_markup=get_legal_kb(), parse_mode='HTML')

    elif q.data == 'legal_accept':
        context.user_data['onboard_done'] = True
        await q.edit_message_text(
            "🏦 <b>Выберите вашу биржу:</b>",
            reply_markup=get_exchange_kb(),
            parse_mode='HTML'
        )

    elif q.data.startswith('exch_'):
        exchange_name = q.data.replace('exch_', '')
        db.update_user(user_id, exchange=exchange_name)
        context.user_data['awaiting_deposit'] = True
        await q.edit_message_text(
            f"✅ Биржа <b>{exchange_name.capitalize()}</b> сохранена!\n\nУкажите депозит (например, <code>1000</code>):",
            parse_mode='HTML'
        )

    elif q.data.startswith('confirm_take_'):
        sig_id = int(q.data.split('_')[2])
        await q.edit_message_reply_markup(reply_markup=get_confirm_take_kb(sig_id))

    elif q.data.startswith('cancel_take_'):
        sig_id = int(q.data.split('_')[2])
        conn = get_conn()
        sig = conn.execute('SELECT coin FROM signals WHERE id=?', (sig_id,)).fetchone()
        conn.close()
        if sig:
            await q.edit_message_reply_markup(reply_markup=get_signal_actions_kb(sig_id, sig['coin'], u.get('exchange', 'binance')))

    elif q.data.startswith('take_'):
        sig_id = int(q.data.split('_')[1])
        conn = get_conn()
        sig_row = conn.execute('SELECT * FROM signals WHERE id=?', (sig_id,)).fetchone()
        conn.close()

        if sig_row:
            sig = {
                'id': sig_id, 'coin': sig_row['coin'], 'signal_type': sig_row['signal_type'],
                'entry_price': sig_row['entry_price'], 'stop_loss': sig_row['stop_loss'],
                'target_prices': json.loads(sig_row['target_prices'])
            }
            paper.auto_open(user_id, sig)
            action = "Лонг" if sig['signal_type'] == 'BUY' else "Шорт"
            await q.edit_message_text(f"✅ <b>Сделка в работу!</b>\nТип: {action}\nБот будет сопровождать её.", parse_mode='HTML')

    elif q.data.startswith('custom_size_'):
        sig_id = int(q.data.split('_')[2])
        context.user_data['awaiting_custom_size'] = True
        context.user_data['custom_size_signal_id'] = sig_id
        await q.edit_message_text("💰 Введите сумму в USDT, на которую вы открыли позицию:")

    elif q.data.startswith('skip_'):
        await q.edit_message_text(f"{q.message.text}\n\n❌ <i>Сигнал пропущен.</i>", parse_mode='HTML')

    elif q.data == 'tariff_pro':
        inv = payment.create_invoice(user_id, 'pro')
        if inv:
            await q.edit_message_text(
                f"💳 <b>Оплата PRO</b>\n\nСумма: <b>{inv['amount']} USDT</b>",
                reply_markup=payment_kb(inv['pay_url'], inv['invoice_id']),
                parse_mode='HTML'
            )
        else:
            await q.edit_message_text("❌ Ошибка создания счета.")

    elif q.data.startswith('check_'):
        invoice_id = int(q.data.split('_')[1])
        if db.invoice_already_used(invoice_id):
            await q.answer("Этот счет уже использован.", show_alert=True)
            return
        if payment.check_invoice(invoice_id, user_id):
            db.mark_invoice_paid(invoice_id, user_id, 'pro')
            expiry = (datetime.now() + timedelta(days=30)).isoformat()
            db.update_user(user_id, tariff='pro', tariff_expiry=expiry)
            await q.edit_message_text("🎉 <b>Оплата получена!</b>\nТариф PRO активирован на 30 дней.", parse_mode='HTML')
        else:
            await q.answer("Оплата еще не поступила. Подождите и нажмите снова.", show_alert=True)


# === ТЕКСТ ===
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    u = db.get_user(update.effective_user.id)

    if context.user_data.get('awaiting_deposit'):
        try:
            amount = float(text.replace(',', '.'))
            if amount <= 0: raise ValueError
            db.update_user(u['user_id'], balance_usdt=amount)
            context.user_data['awaiting_deposit'] = False
            await update.message.reply_text(
                f"✅ Баланс установлен: <b>{amount:.2f} USDT</b>.",
                reply_markup=get_reply_main_menu(u['user_id']), parse_mode='HTML'
            )
        except ValueError:
            await update.message.reply_text("❌ Введите число.")
        return

    if context.user_data.get('awaiting_custom_size'):
        try:
            amount = float(text.replace(',', '.'))
            if amount <= 0: raise ValueError
            sig_id = context.user_data['custom_size_signal_id']
            conn = get_conn()
            sig_row = conn.execute('SELECT * FROM signals WHERE id=?', (sig_id,)).fetchone()
            conn.close()
            if sig_row:
                sig = {
                    'id': sig_id, 'coin': sig_row['coin'], 'signal_type': sig_row['signal_type'],
                    'entry_price': sig_row['entry_price'], 'stop_loss': sig_row['stop_loss'],
                    'target_prices': json.loads(sig_row['target_prices'])
                }
                paper.auto_open(u['user_id'], sig, custom_size=amount)
                await update.message.reply_text(f"✅ Сделка по {sig['coin']} открыта на ${amount:.2f}.")
            context.user_data['awaiting_custom_size'] = False
        except ValueError:
            await update.message.reply_text("❌ Введите число.")
        return

    if text == "📊 Сигналы":
        await top_signals_cmd(update, context)
    elif text == "💎 Тарифы":
        await update.message.reply_text("💎 <b>Тарифы</b>\n\nFree - 3 сигнала/день (BTC, ETH)\nPRO - $30/мес (все монеты)", reply_markup=tariffs_kb(), parse_mode='HTML')
    elif text == "💼 Мой профит":
        trades = db.get_open_trades(u['user_id'])
        await update.message.reply_text(f"💼 Открытых сделок: {len(trades)}")
    else:
        await update.message.reply_text("Пожалуйста, пользуйтесь кнопками меню 👇", reply_markup=get_reply_main_menu(u['user_id']))


# === ЗАПУСК ===
async def post_init(app: Application):
    asyncio.create_task(tracker.monitor(app.bot))


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    print("ShiperSignal запущен!")
    app.run_polling()


if __name__ == '__main__':
    main()
