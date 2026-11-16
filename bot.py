import asyncio, logging, json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from config import *
from database import Database, get_conn
from signals import SignalGenerator
from keyboards import *
from tracker import TradeTracker, PaperTrader
from chart_generator import generate_signal_chart
from payments import CryptoBotPayment
import requests
import ccxt

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
db = Database()
sig_gen = SignalGenerator(db)
tracker = TradeTracker(db)
paper = PaperTrader(db)
payment = CryptoBotPayment()
exchange = ccxt.binance()

# === СТАРТ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.add_user(u.id, u.username or '', u.first_name or '')
    user = db.get_user(u.id)

    if u.id in ADMIN_IDS:
        db.update_user(u.id, tariff='pro', tariff_expiry='2099-12-31T23:59:59')
        user['tariff'] = 'pro'
    else:
        # Проверка окончания подписки
        if user['tariff'] in ['pro', 'pro_week', 'pro_month'] and user['tariff_expiry']:
            if datetime.fromisoformat(user['tariff_expiry']) < datetime.now():
                db.update_user(u.id, tariff='free')
                user['tariff'] = 'free'

    # Если депозит не введен
    if user['balance_usdt'] == 0:
        if not context.user_data.get('onboard_done'):
            instruction = f"👋 <b>Привет, {u.first_name}!</b>\n\nНажми кнопку ниже, чтобы ознакомиться с инструкцией."
            await update.message.reply_text(instruction, reply_markup=get_onboarding_kb(), parse_mode='HTML')
            return
        
        context.user_data['awaiting_deposit'] = True
        await update.message.reply_text("💰 Укажите ваш депозит для расчета рисков (например, <code>1000</code>):", parse_mode='HTML')
        return

    await update.message.reply_text(
        f"👋 С возвращением, {u.first_name}!\nВаш депозит: {user['balance_usdt']:.2f} USDT",
        reply_markup=get_reply_main_menu(u.id, user.get('trial_used', 0))
    )

# === СИГНАЛЫ ===
async def top_signals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = db.get_user(update.effective_user.id)
    
    if u['tariff'] == 'free' and context.user_data.get('signals_today', 0) >= 3:
        await update.message.reply_text("🛑 <b>Лимит бесплатных сигналов (3/3) исчерпан.</b>\n\nОформите PRO, чтобы торговать без ограничений по всем 80+ монетам!", reply_markup=tariffs_kb(), parse_mode='HTML')
        return

    coins = ['BTC', 'ETH'] if u['tariff'] == 'free' else ALL_COINS
    await update.message.reply_text("⏳ Сканирую 80+ монет по 3 таймфреймам...")
    sigs = sig_gen.scan(coins, '15м')
    
    if not sigs:
        text = "😴 <b>Сейчас нет идеальных сетапов (оценка A+).</b>\nМы не даем сигналы, когда рынок шумит."
        if u['tariff'] == 'free':
            text += "\n\n💎 <i>В PRO-версии бот сканирует 80+ монет и находит больше сетапов.</i>"
        await update.message.reply_text(text, reply_markup=tariffs_kb() if u['tariff'] == 'free' else None, parse_mode='HTML')
        return
        
    context.user_data['signals_today'] = context.user_data.get('signals_today', 0) + 1
    
    s = sigs[0]
    text = sig_gen.format(s, user_balance=u.get('balance_usdt', 1000))
    
    if u['tariff'] == 'free':
        text += "\n\n⚠️ <i>Вы получаете 3 сигнала в день по BTC/ETH.</i>\n🚀 <b>Оформите PRO</b> для доступа ко всем монетам!"
        
    kb = get_signal_actions_kb(s['id'])
    chart = generate_signal_chart(s['coin'], s['signal_type'], s['entry_price'], s['stop_loss'], s['target_prices'][0])

    if chart:
        await update.message.reply_photo(photo=chart, caption=text, reply_markup=kb, parse_mode='HTML')
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode='HTML')

# === МОИ СДЕЛКИ ===
async def my_trades_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = db.get_user(update.effective_user.id)
    trades = db.get_open_trades(u['user_id'])
    
    if not trades:
        await update.message.reply_text("У вас нет открытых сделок.")
        return
        
    text = "🟢 <b>Ваши открытые сделки:</b>\n\n"
    for t in trades:
        conn = get_conn()
        sig = conn.execute('SELECT coin, signal_type FROM signals WHERE id=?', (t['signal_id'],)).fetchone()
        conn.close()
        if sig:
            text += f"• <b>{sig['coin']}</b> ({sig['signal_type']}) | Вход: ${t['entry_price']:.4g}\n"
            
    await update.message.reply_text(text, parse_mode='HTML')

# === АДМИН-ПАНЕЛЬ ===
async def send_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE, mode='main'):
    users = db.get_all_users()
    
    if mode == 'last_50':
        filtered_users = users[-50:]
        title = "👥 <b>Последние 50 пользователей</b>"
    elif mode == 'only_paid':
        filtered_users = [u for u in users if u['tariff'] in ['pro', 'pro_week', 'pro_month']]
        title = "💎 <b>Пользователи с подпиской PRO</b>"
    else:
        filtered_users = users
        title = "👑 <b>Админ-панель</b>"

    total_users = len(users)
    pro_users = sum(1 for u in users if u['tariff'] in ['pro', 'pro_week', 'pro_month'])
    
    header = f"{title}\n\nВсего юзеров: <b>{total_users}</b>\nОплатили (PRO): <b>{pro_users}</b>\n\n"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(header, reply_markup=get_admin_kb(), parse_mode='HTML')
        chat_id = update.effective_chat.id
    else:
        await update.message.reply_text(header, reply_markup=get_admin_kb(), parse_mode='HTML')
        chat_id = update.effective_chat.id

    if mode != 'main':
        if not filtered_users:
            await context.bot.send_message(chat_id=chat_id, text="Список пуст.")
            return
            
        chunk_size = 30
        chunks = [filtered_users[i:i + chunk_size] for i in range(0, len(filtered_users), chunk_size)]
        
        for i, chunk in enumerate(chunks):
            user_list = f"<b>Стр. {i+1} из {len(chunks)}:</b>\n\n"
            for usr in chunk:
                pay_status = "✅" if usr['tariff'] in ['pro', 'pro_week', 'pro_month'] else "🆓"
                user_list += f"{pay_status} <code>{usr['user_id']}</code> | Депозит: {usr.get('balance_usdt', 0):.1f} $\n"
            await context.bot.send_message(chat_id=chat_id, text=user_list, parse_mode='HTML')

# === CALLBACKS ===
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    u = db.get_user(user_id)
    
    if not u:
        await q.edit_message_text("Ошибка. Нажмите /start")
        return

    if user_id in ADMIN_IDS:
        db.update_user(user_id, tariff='pro', tariff_expiry='2099-12-31T23:59:59')
        u['tariff'] = 'pro'

    # --- АДМИНКА ---
    if q.data == 'admin_last_50':
        await send_admin_panel(update, context, mode='last_50')
        return
    elif q.data == 'admin_only_paid':
        await send_admin_panel(update, context, mode='only_paid')
        return
    elif q.data == 'admin_give_pro':
        context.user_data['awaiting_pro_id'] = True
        await q.edit_message_text("🎁 <b>Выдача PRO</b>\n\nОтправьте ID пользователя:")
        return
    elif q.data.startswith('give_pro_'):
        _, _, days, target_id = q.data.split('_')
        days = int(days)
        target_id = int(target_id)
        
        expiry = (datetime.now() + timedelta(days=days)).isoformat()
        db.update_user(target_id, tariff='pro', tariff_expiry=expiry)
        await q.edit_message_text(f"✅ Пользователю <code>{target_id}</code> выдан PRO на {days} дней!", parse_mode='HTML')
        return
    elif q.data == 'admin_broadcast':
        context.user_data['awaiting_broadcast'] = True
        await q.edit_message_text("📢 <b>Режим рассылки</b>\n\nОтправьте текст для рассылки:")
        return
    elif q.data == 'admin_backtest':
        await q.edit_message_text("🧪 <b>Запускаю бэктест BTC/USDT за последние 1000 свечей...</b>\nЭто займет около 1-2 минут.")
        
        from backtester import Backtester
        bt = Backtester()
        
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: bt.run('BTC', '15м', 20))
        
        if res:
            text = f"📊 <b>Результаты бэктеста (BTC/15м)</b>\n\n" \
                   f"Всего сигналов: {res['total']}\n" \
                   f"Успешных (TP1): {res['wins']}\n" \
                   f"Убыточных (Стоп): {res['losses']}\n\n" \
                   f"🏆 <b>Винрейт: {res['winrate']:.1f}%</b>"
            await q.edit_message_text(text, parse_mode='HTML')
        else:
            await q.edit_message_text("❌ Не удалось собрать данные для бэктеста.")
        return

    # --- ОСТАЛЬНОЕ ---
    if q.data == 'main_menu':
        await q.message.reply_text("👋 Главное меню:", reply_markup=get_reply_main_menu(user_id, u.get('trial_used', 0)))
        return
    elif q.data == 'onboard_read':
        await q.edit_message_text(LEGAL_DISCLAIMER, reply_markup=get_legal_kb(), parse_mode='HTML')
    elif q.data == 'legal_accept':
        context.user_data['onboard_done'] = True
        await q.edit_message_text("🏦 <b>Выберите вашу биржу:</b>", reply_markup=get_exchange_kb(), parse_mode='HTML')
    elif q.data.startswith('exch_'):
        exch = q.data.replace('exch_', '')
        db.update_user(user_id, exchange=exch)
        context.user_data['awaiting_deposit'] = True
        await q.edit_message_text(f"✅ Биржа сохранена!\n\nУкажите ваш депозит (например, 1000):", parse_mode='HTML')
    elif q.data == 'change_exch':
        await q.edit_message_text("🏦 <b>Выберите новую биржу:</b>", reply_markup=get_exchange_kb(), parse_mode='HTML')
    elif q.data == 'change_deposit':
        context.user_data['awaiting_deposit'] = True
        await q.edit_message_text("💰 Введите новую сумму депозита (например, 1000):", parse_mode='HTML')

    elif q.data == 'activate_trial':
        if u['trial_used']:
            await q.answer("❌ Вы уже использовали пробный период!", show_alert=True)
            return
        expiry = (datetime.now() + timedelta(days=3)).isoformat()
        db.update_user(user_id, tariff='pro', tariff_expiry=expiry, trial_used=1)
        await q.edit_message_text("🎉 <b>Пробный PRO активирован на 3 дня!</b>", parse_mode='HTML')

    elif q.data.startswith('take_'):
        sig_id = int(q.data.split('_')[1])
        conn = get_conn()
        sig_row = conn.execute('SELECT * FROM signals WHERE id=?', (sig_id,)).fetchone()
        conn.close()
        if sig_row:
            sig = {
                'id': sig_id, 'coin': sig_row['coin'], 'signal_type': sig_row['signal_type'], 
                'entry_price': sig_row['entry_price'], 'stop_loss': sig_row['stop_loss'], 
                'target_prices': json.loads(sig_row['target_prices']), 'confidence': sig_row['confidence']
            }
            paper.auto_open(user_id, sig)
            
            current_text = q.message.caption or q.message.text
            new_text = current_text + "\n\n✅ <b>Сделка взята в работу</b>"
            
            try:
                await q.edit_message_caption(caption=new_text, reply_markup=None, parse_mode='HTML')
            except Exception:
                await q.edit_message_text(text=new_text, reply_markup=None, parse_mode='HTML')
            
    elif q.data.startswith('skip_'):
        current_text = q.message.caption or q.message.text
        new_text = current_text + "\n\n❌ <b>Сделка пропущена</b>"
        
        try:
            await q.edit_message_caption(caption=new_text, reply_markup=None, parse_mode='HTML')
        except Exception:
            await q.edit_message_text(text=new_text, reply_markup=None, parse_mode='HTML')

    elif q.data == 'lessons_menu':
        await q.edit_message_text("🎓 <b>База знаний ShiperSignal</b>\n\nВыберите уровень обучения:", reply_markup=get_lessons_levels_kb(), parse_mode='HTML')
    elif q.data.startswith('level_'):
        level_prefix = q.data.replace('level_', '')
        done = json.loads(u.get('lessons_done', '[]'))
        await q.edit_message_text(f"🎓 <b>Уроки уровня {level_prefix[-1]}</b>", reply_markup=get_level_lessons_kb(level_prefix, done), parse_mode='HTML')
    elif q.data.startswith('lesson_'):
        key = q.data.split('_', 1)[1] 
        if key in LESSONS:
            db.mark_lesson_done(user_id, key)
            level_prefix = key.split('_')[0]
            await q.edit_message_text(LESSONS[key]['text'], reply_markup=get_lesson_back_kb(level_prefix), parse_mode='HTML')

    elif q.data == 'trade_history':
        trades = db.get_closed_trades(user_id, 5)
        if not trades:
            await q.edit_message_text("📜 История пуста.")
            return
        text = "📜 <b>Последние сделки:</b>\n\n"
        for t in trades:
            text += f"• {t['coin']} ({t['signal_type']}): {t['notes']}\n"
        await q.edit_message_text(text, parse_mode='HTML')

    elif q.data.startswith('tariff_pro'):
        tariff_key = 'pro_week' if 'week' in q.data else 'pro_month'
        inv = payment.create_invoice(user_id, tariff_key)
        if inv:
            await q.edit_message_text(f"💳 <b>Оплата {TARIFFS[tariff_key]['name']}</b>\nСумма: <b>{inv['amount']} USDT</b>", reply_markup=payment_kb(inv['pay_url'], inv['invoice_id']), parse_mode='HTML')
        else:
            await q.edit_message_text("❌ Ошибка создания счета.")
            
    elif q.data.startswith('check_'):
        invoice_id = int(q.data.split('_')[1])
        if db.invoice_already_used(invoice_id):
            await q.answer("Счет уже использован.", show_alert=True)
            return
        
        if payment.check_invoice(invoice_id, user_id):
            db.mark_invoice_paid(invoice_id, user_id, 'pro')
            
            res = requests.get(f"https://pay.crypt.bot/api/getInvoices", headers=payment.headers, params={'invoice_ids': str(invoice_id)}).json()
            inv = res['result']['items'][0]
            days = 7 if 'week' in inv['payload'] else 30
            
            expiry = (datetime.now() + timedelta(days=days)).isoformat()
            db.update_user(user_id, tariff='pro', tariff_expiry=expiry)
            await q.edit_message_text("🎉 <b>Оплата получена!</b>\nТариф PRO активирован.", parse_mode='HTML')
        else:
            await q.answer("❌ Оплата не найдена! Подождите 1-2 минуты и нажмите снова.", show_alert=True)

# === ТЕКСТ ===
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    u = db.get_user(user_id)

    if not u:
        await update.message.reply_text("Нажмите /start")
        return

    if user_id in ADMIN_IDS:
        db.update_user(user_id, tariff='pro', tariff_expiry='2099-12-31T23:59:59')
        u['tariff'] = 'pro'

        if context.user_data.get('awaiting_pro_id'):
            try:
                target_id = int(text)
                context.user_data['awaiting_pro_id'] = False
                await update.message.reply_text(f"Выберите срок для <code>{target_id}</code>:", reply_markup=get_admin_give_pro_kb(target_id), parse_mode='HTML')
            except ValueError:
                await update.message.reply_text("❌ Введите числовой ID.")
            return

        if context.user_data.get('awaiting_broadcast'):
            context.user_data['awaiting_broadcast'] = False
            users = db.get_all_users()
            success, fail = 0, 0
            await update.message.reply_text(f"⏳ Начинаю рассылку...")
            for usr in users:
                try:
                    await context.bot.send_message(chat_id=usr['user_id'], text=text, parse_mode='HTML')
                    success += 1
                except Exception:
                    fail += 1
            await update.message.reply_text(f"✅ <b>Рассылка завершена!</b>\nДоставлено: {success}\nНе дошло: {fail}", parse_mode='HTML')
            return

    if context.user_data.get('awaiting_deposit'):
        try:
            amount = float(text.replace(',', '.'))
            db.update_user(user_id, balance_usdt=amount)
            context.user_data['awaiting_deposit'] = False
            u = db.get_user(user_id)
            await update.message.reply_text(f"✅ Депозит установлен: <b>{amount:.2f} USDT</b>.", reply_markup=get_reply_main_menu(user_id, u.get('trial_used', 0)), parse_mode='HTML')
        except ValueError:
            await update.message.reply_text("❌ Введите число.")
        return

    if text == "🎁 Пробный PRO (3 дня)":
        if u['trial_used']:
            await update.message.reply_text("❌ Вы уже использовали пробный период!")
            return
        expiry = (datetime.now() + timedelta(days=3)).isoformat()
        db.update_user(user_id, tariff='pro', tariff_expiry=expiry, trial_used=1)
        await update.message.reply_text("🎉 <b>Пробный PRO активирован на 3 дня!</b>", reply_markup=get_reply_main_menu(user_id, 1), parse_mode='HTML')

    elif text == "📊 Сигналы": 
        await top_signals_cmd(update, context)
    elif text == "🟢 Мои сделки":
        await my_trades_cmd(update, context)
    elif text == "💎 Тарифы": 
        await update.message.reply_text("💎 <b>Тарифы</b>\n\nВыберите подходящий:", reply_markup=tariffs_kb(), parse_mode='HTML')
    elif text == "🎓 Обучение": 
        await update.message.reply_text("🎓 <b>База знаний:</b>", reply_markup=get_lessons_levels_kb(), parse_mode='HTML')
    elif text == "👤 Профиль":
        kb = get_profile_kb()
        await update.message.reply_text(
            f"👤 <b>Профиль</b>\n\nID: <code>{u['user_id']}</code>\nТариф: <b>{u['tariff'].upper()}</b>\nБиржа: {u.get('exchange', 'binance').capitalize()}\nДепозит: {u.get('balance_usdt', 0):.2f} USDT",
            reply_markup=kb, parse_mode='HTML')
    elif text == "💬 Чат трейдеров":
        if u['tariff'] in ['pro', 'pro_week', 'pro_month']:
            await update.message.reply_text("💬 <b>Закрытый чат трейдеров</b>\n\nВаш доступ подтвержден. Мы завершаем настройку безопасности.\n\n🚀 Скоро вы получите приглашение.", parse_mode='HTML')
        else:
            await update.message.reply_text("🔒 <b>Доступ ограничен.</b>\n\nЧат трейдеров доступен только для подписчиков тарифа <b>PRO</b>.", parse_mode='HTML')
    elif text == "🆘 Поддержка":
        await update.message.reply_text(f"🆘 <b>Служба поддержки</b>\n\nНапишите нам: {SUPPORT_LINK}", parse_mode='HTML')
    elif text == "🌅 Дайджест":
        await update.message.reply_text("⏳ Собираю данные...")
        try:
            btc = exchange.fetch_ticker('BTC/USDT')
            eth = exchange.fetch_ticker('ETH/USDT')
            fg = requests.get('https://api.alternative.me/fng/').json()['data'][0]
            
            tickers = exchange.fetch_tickers(['SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'DOGE/USDT', 'AVAX/USDT'])
            sorted_tickers = sorted(tickers.values(), key=lambda x: x['percentage'], reverse=True)
            top_up = ", ".join([f"{t['symbol'].split('/')[0]} (+{t['percentage']:.1f}%)" for t in sorted_tickers[:2]])
            top_down = ", ".join([f"{t['symbol'].split('/')[0]} ({t['percentage']:.1f}%)" for t in sorted_tickers[-2:]])
            
            msg = f"🌅 <b>Дайджест рынка</b>\n\n🟠 BTC: ${btc['last']:,.0f} ({btc['percentage']:+.1f}%)\n🔵 ETH: ${eth['last']:,.0f} ({eth['percentage']:+.1f}%)\n\n😱 <b>Fear & Greed:</b> {fg['value']} ({fg['value_classification']})\n\n🚀 <b>Растут:</b> {top_up}\n📉 <b>Падают:</b> {top_down}"
            
            if u['tariff'] == 'free':
                msg += "\n\n💎 <i>Хотите получать полную картину и все сигналы? Оформите PRO.</i>"
                
            await update.message.reply_text(msg, reply_markup=tariffs_kb() if u['tariff'] == 'free' else None, parse_mode='HTML')
        except Exception:
            await update.message.reply_text("⚠️ Ошибка получения данных.")
            
    elif text == "👑 Админ-панель" and u['user_id'] in ADMIN_IDS:
        await send_admin_panel(update, context, mode='main')
    else:
        await update.message.reply_text("Пользуйтесь кнопками меню 👇", reply_markup=get_reply_main_menu(u['user_id'], u.get('trial_used', 0)))

# === УТРЕННИЙ ДАЙДЖЕСТ ===
async def morning_digest_job(app):
    while True:
        now = datetime.now()
        if now.hour == 9 and now.minute == 0:
            users = db.get_all_users()
            try:
                btc = exchange.fetch_ticker('BTC/USDT')
                fg = requests.get('https://api.alternative.me/fng/').json()['data'][0]
                msg = f"🌅 <b>Доброе утро!</b>\n\n🟠 BTC: ${btc['last']:,.0f}\n😱 F&G: {fg['value']}\n\nУдачного дня!"
                for u in users:
                    try: await app.bot.send_message(u['user_id'], msg, parse_mode='HTML')
                    except: pass
            except: pass
            await asyncio.sleep(86400)
        else:
            await asyncio.sleep(60)

async def post_init(app: Application):
    asyncio.create_task(tracker.monitor(app.bot))
    asyncio.create_task(morning_digest_job(app))

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))
    print("ShiperSignal (Sniper Edition) запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()
