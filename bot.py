import asyncio, logging, json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from config import *
from database import Database, get_conn
from signals import SignalGenerator
from keyboards import *
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
    db.add_user(u.id, u.username or '', u.first_name or '')
    user = db.get_user(u.id)

    if u.id in ADMIN_IDS:
        db.update_user(u.id, tariff='pro', tariff_expiry='2099-12-31T23:59:59')

    if not context.user_data.get('onboard_done'):
        instruction = f"👋 <b>Привет, {u.first_name}!</b>\n\nНажми кнопку ниже, чтобы ознакомиться с инструкцией."
        await update.message.reply_text(instruction, reply_markup=get_onboarding_kb(), parse_mode='HTML')
        return

    if user['balance_usdt'] == 0:
        context.user_data['awaiting_deposit'] = True
        await update.message.reply_text("💰 Укажите ваш депозит (например, <code>1000</code>):", parse_mode='HTML')
        return

    await update.message.reply_text("👋 Главное меню:", reply_markup=get_reply_main_menu(u.id))

# === СИГНАЛЫ ===
async def top_signals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = db.get_user(update.effective_user.id)
    
    if u['tariff'] == 'free' and context.user_data.get('signals_today', 0) >= 3:
        await update.message.reply_text("🛑 <b>Лимит (3/3) исчерпан.</b>\n\nОформите PRO для доступа к 80+ монетам.", parse_mode='HTML')
        return

    coins = ['BTC', 'ETH'] if u['tariff'] == 'free' else ALL_COINS[:10]
    await update.message.reply_text("⏳ Сканирую рынок...")
    sigs = sig_gen.scan(coins, '15м')
    
    if not sigs:
        await update.message.reply_text("😴 Нет сетапов.")
        return
        
    context.user_data['signals_today'] = context.user_data.get('signals_today', 0) + 1
    
    s = sigs[0]
    text = sig_gen.format(s, user_balance=u.get('balance_usdt', 1000), exchange_name=u.get('exchange', 'binance'))
    kb = get_signal_actions_kb(s['id'], s['coin'], u.get('exchange', 'binance'))
    chart = generate_signal_chart(s['coin'], s['signal_type'], s['entry_price'], s['stop_loss'], s['target_prices'][0])

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
        await q.edit_message_text("🏦 <b>Выберите вашу биржу:</b>", reply_markup=get_exchange_kb(), parse_mode='HTML')
    elif q.data.startswith('exch_'):
        exch = q.data.replace('exch_', '')
        db.update_user(user_id, exchange=exch)
        context.user_data['awaiting_deposit'] = True
        await q.edit_message_text(f"✅ Биржа {exch.capitalize()} сохранена!\n\nУкажите депозит:", parse_mode='HTML')
        
    elif q.data == 'change_exch':
        await q.edit_message_text("🏦 <b>Выберите новую биржу:</b>", reply_markup=get_exchange_kb(), parse_mode='HTML')

    elif q.data == 'activate_trial':
        if u['trial_used']:
            await q.answer("❌ Вы уже использовали пробный период!", show_alert=True)
            return
        expiry = (datetime.now() + timedelta(days=3)).isoformat()
        db.update_user(user_id, tariff='pro', tariff_expiry=expiry, trial_used=1)
        await q.edit_message_text("🎉 <b>Пробный PRO активирован на 3 дня!</b>\n\nВсе ограничения сняты.", parse_mode='HTML')

    elif q.data.startswith('take_'):
        sig_id = int(q.data.split('_')[1])
        conn = get_conn()
        sig_row = conn.execute('SELECT * FROM signals WHERE id=?', (sig_id,)).fetchone()
        conn.close()
        if sig_row:
            sig = {'id': sig_id, 'coin': sig_row['coin'], 'signal_type': sig_row['signal_type'], 'entry_price': sig_row['entry_price'], 'stop_loss': sig_row['stop_loss'], 'target_prices': json.loads(sig_row['target_prices'])}
            paper.auto_open(user_id, sig)
            await q.edit_message_text(f"✅ <b>Сигнал ПРИНЯТ в работу.</b>\n\nБот будет сопровождать сделку и пришлет уведомления.", parse_mode='HTML')
            
    elif q.data.startswith('skip_'):
        await q.edit_message_text(f"❌ <b>Сигнал ПРОПУЩЕН.</b>", parse_mode='HTML')

    elif q.data == 'lessons_menu':
        done = json.loads(u.get('lessons_done', '[]'))
        await q.edit_message_text("🎓 <b>Выберите урок:</b>", reply_markup=get_lessons_kb(done), parse_mode='HTML')
        
    elif q.data.startswith('lesson_'):
        key = q.data.split('_')[1]
        if key in LESSONS:
            db.mark_lesson_done(user_id, key)
            await q.edit_message_text(LESSONS[key]['text'], reply_markup=get_lesson_back_kb(), parse_mode='HTML')

    elif q.data == 'trade_history':
        trades = db.get_closed_trades(user_id, 5)
        if not trades:
            await q.edit_message_text("📜 История пуста.")
            return
        text = "📜 <b>Последние сделки:</b>\n\n"
        for t in trades:
            emoji = "✅" if t['realized_pnl'] > 0 else "🛑"
            text += f"{emoji} {t['coin']} ({t['signal_type']}): {t['realized_pnl']:+.2f} USDT\n"
        await q.edit_message_text(text, parse_mode='HTML')

    elif q.data == 'tariff_pro':
        inv = payment.create_invoice(user_id, 'pro')
        if inv:
            await q.edit_message_text(f"💳 <b>Оплата PRO</b>\nСумма: <b>{inv['amount']} USDT</b>", reply_markup=payment_kb(inv['pay_url'], inv['invoice_id']), parse_mode='HTML')
        else:
            await q.edit_message_text("❌ Ошибка создания счета.")
            
    elif q.data.startswith('check_'):
        invoice_id = int(q.data.split('_')[1])
        if db.invoice_already_used(invoice_id):
            await q.answer("Счет уже использован.", show_alert=True)
            return
        if payment.check_invoice(invoice_id, user_id):
            db.mark_invoice_paid(invoice_id, user_id, 'pro')
            expiry = (datetime.now() + timedelta(days=30)).isoformat()
            db.update_user(user_id, tariff='pro', tariff_expiry=expiry)
            await q.edit_message_text("🎉 <b>Оплата получена!</b>\nТариф PRO активирован.", parse_mode='HTML')
        else:
            await q.answer("Оплата не найдена. Подождите.", show_alert=True)

# === ТЕКСТ ===
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    u = db.get_user(update.effective_user.id)

    if u['user_id'] in ADMIN_IDS:
        db.update_user(u['user_id'], tariff='pro', tariff_expiry='2099-12-31T23:59:59')

    if context.user_data.get('awaiting_deposit'):
        try:
            amount = float(text.replace(',', '.'))
            db.update_user(u['user_id'], balance_usdt=amount)
            context.user_data['awaiting_deposit'] = False
            await update.message.reply_text(f"✅ Баланс: <b>{amount:.2f} USDT</b>.", reply_markup=get_reply_main_menu(u['user_id']), parse_mode='HTML')
        except ValueError:
            await update.message.reply_text("❌ Введите число.")
        return

    if text == "📊 Сигналы": 
        await top_signals_cmd(update, context)
    elif text == "💎 Тарифы": 
        await update.message.reply_text("💎 <b>Тарифы</b>\n\nPRO - $30/мес (все монеты)", reply_markup=tariffs_kb(), parse_mode='HTML')
    elif text == "🎓 Обучение": 
        done = json.loads(u.get('lessons_done', '[]'))
        await update.message.reply_text("🎓 <b>База знаний:</b>", reply_markup=get_lessons_kb(done), parse_mode='HTML')
    elif text == "👤 Профиль":
        kb = get_profile_kb()
        if u['tariff'] == 'free' and not u['trial_used']:
            kb.inline_keyboard.insert(0, [InlineKeyboardButton("🎁 Пробный PRO (3 дня)", callback_data='activate_trial')])
            
        await update.message.reply_text(
            f"👤 <b>Профиль</b>\n\nID: <code>{u['user_id']}</code>\nТариф: <b>{u['tariff'].upper()}</b>\nБиржа: {u.get('exchange', 'binance').capitalize()}\nБаланс: {u.get('balance_usdt', 0):.2f} USDT",
            reply_markup=kb, parse_mode='HTML')
    elif text == "💼 Мой профит":
        trades = db.get_closed_trades(u['user_id'], 100)
        pnl = sum(t['realized_pnl'] for t in trades)
        wins = sum(1 for t in trades if t['realized_pnl'] > 0)
        total = len(trades)
        winrate = (wins / total * 100) if total > 0 else 0
        
        await update.message.reply_text(
            f"💼 <b>Статистика</b>\n\nБаланс: <b>{u.get('balance_usdt', 1000):.2f} USDT</b>\nPnL: <b>{pnl:+.2f} USDT</b>\nСделок: {total} | Винрейт: <b>{winrate:.1f}%</b>",
            parse_mode='HTML')
    elif text == "💬 Чат трейдеров":
        if u['tariff'] in ['pro', 'vip']:
            await update.message.reply_text(f"💬 <b>Закрытый чат</b>\n\nВаш доступ подтвержден.\nСсылка: {CHAT_LINK}", parse_mode='HTML')
        else:
            await update.message.reply_text("🔒 <b>Доступ ограничен.</b>\n\nЧат доступен только для PRO.", parse_mode='HTML')
    elif text == "🆘 Поддержка":
        await update.message.reply_text(f"🆘 <b>Служба поддержки</b>\n\nНапишите нам: {SUPPORT_LINK}", parse_mode='HTML')
    elif text == "👑 Админ-панель" and u['user_id'] in ADMIN_IDS:
        users = db.get_all_users()
        await update.message.reply_text(f"👑 <b>Админ-панель</b>\n\nВсего пользователей: {len(users)}", parse_mode='HTML')
    else:
        await update.message.reply_text("Пользуйтесь кнопками меню 👇", reply_markup=get_reply_main_menu(u['user_id']))

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
