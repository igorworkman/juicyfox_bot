@router.callback_query(F.data.startswith('pay:'))
async def choose_cur(cq: CallbackQuery):
    plan = cq.data.split(':')[1]
    amt = TARIFFS[plan]
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f'payc:{plan}:{c}')
    kb.button(text=tr(cq.from_user.language_code, 'back'), callback_data='back_to_menu')
    kb.adjust(2)
    await cq.message.edit_text(
        tr(cq.from_user.language_code, 'choose_cur', amount=amt),
        reply_markup=kb.as_markup()
    )

@router.callback_query(F.data.startswith('payc:'))
async def pay_make(cq:CallbackQuery):
    _,plan,cur=cq.data.split(':'); amt=TARIFFS[plan]
    url=await create_invoice(cq.from_user.id, amt, cur, 'JuicyFox Subscription', pl=plan)
    if url:
        await cq.message.edit_text(f"Счёт на оплату ({plan.upper()}): {url}")
        
    else:
        await cq.answer(tr(cq.from_user.language_code,'inv_err'),show_alert=True)

# ---- Donate FSM ----
class Donate(StatesGroup): choosing_currency=State(); entering_amount=State()

@donate_r.callback_query(F.data=='donate')
async def donate_currency(cq:CallbackQuery,state:FSMContext):
    kb=InlineKeyboardBuilder();
    for t,c in CURRENCIES: kb.button(text=t,callback_data=f'doncur:{c}')
    kb.adjust(2)
    await cq.message.edit_text(tr(cq.from_user.language_code,'choose_cur',amount='donate'),reply_markup=kb.as_markup())
    await state.set_state(Donate.choosing_currency)

@donate_r.callback_query(F.data.startswith('doncur:'),Donate.choosing_currency)
async def donate_amount(cq: CallbackQuery, state: FSMContext):
    """Отображаем просьбу ввести сумму + кнопка 🔙 Назад"""
    await state.update_data(currency=cq.data.split(':')[1])
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text='🔙 Назад', callback_data='don_back')]]
    )
    await cq.message.edit_text(
        tr(cq.from_user.language_code, 'don_enter'),
        reply_markup=back_kb
    )
    await state.set_state(Donate.entering_amount)

# --- кнопка Назад из ввода суммы ---
@donate_r.callback_query(F.data=='don_back', Donate.entering_amount)
async def donate_back(cq: CallbackQuery, state: FSMContext):
    """Возврат к выбору валюты"""
    await state.set_state(Donate.choosing_currency)
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f'doncur:{c}')
    kb.adjust(2)
    await cq.message.edit_text(
        tr(cq.from_user.language_code, 'choose_cur', amount='donate'),
        reply_markup=kb.as_markup()
    )

@dp.message(Donate.entering_amount)
async def donate_finish(msg: Message, state: FSMContext):
    """Получаем сумму в USD, создаём счёт и завершаем FSM"""
    text = msg.text.replace(',', '.').strip()
    if not text.replace('.', '', 1).isdigit():
        await msg.reply(tr(msg.from_user.language_code, 'don_num'))
        return
    usd = float(text)
    data = await state.get_data()
    cur  = data['currency']
    url  = await create_invoice(msg.from_user.id, usd, cur, 'JuicyFox Donation', pl='donate')
    if url:
        await msg.answer(f"Счёт на оплату (Donate): {url}")
    else:
        await msg.reply(tr(msg.from_user.language_code, 'inv_err'))
    await state.clear()

# ---------------- Cancel / Отмена -------------------------
@dp.message(Command('cancel'))
async def cancel_any(msg: Message, state: FSMContext):
    """Команда /cancel сбрасывает текущее состояние и возвращает меню"""
    if await state.get_state():
        await state.clear()
        await msg.answer(tr(msg.from_user.language_code, 'cancel'))
        await cmd_start(msg)  # показать меню заново
    else:
        await msg.answer(tr(msg.from_user.language_code, 'nothing_cancel'))

# ---------------- Main menu / live ------------------------
@main_r.message(Command('start'))
async def cmd_start(m: Message):
        # если пользователь застрял в FSM (донат), сбрасываем
    state = dp.fsm.get_context(bot, chat_id=m.chat.id, user_id=m.from_user.id)
    if await state.get_state():
        await state.clear()
    lang = m.from_user.language_code
    kb = InlineKeyboardBuilder()
    kb.button(text=tr(lang, 'btn_live'),   callback_data='live')
    kb.button(text=tr(lang, 'btn_club'),   callback_data='pay:club')
    kb.button(text=tr(lang, 'btn_vip'),    callback_data='pay:vip')
    kb.button(text=tr(lang, 'btn_chat'),   callback_data='pay:chat')
    kb.button(text=tr(lang, 'btn_donate'), callback_data='donate')
    kb.adjust(1)
    await m.answer(tr(lang, 'menu'), reply_markup=kb.as_markup())

@main_r.callback_query(F.data == 'live')
async def live_link(cq: CallbackQuery):
    await cq.message.edit_text(tr(cq.from_user.language_code, 'live', live_link=LIVE_CHANNEL_URL))

# ---------------- Relay private ↔ group -------------------
@dp.message((F.chat.type == 'private') & (~F.text.startswith('/')))
async def relay_private(msg: Message):
    if not await is_paid(msg.from_user.id):
        await msg.reply(tr(msg.from_user.language_code, 'not_paid'))
        return

    # Формируем шапку
    expires = await expire_date_str(msg.from_user.id)
    donated = await total_donated(msg.from_user.id)
    flag = {
        'ru': '🇷🇺', 'en': '🇺🇸', 'tr': '🇹🇷', 'de': '🇩🇪'
    }.get(msg.from_user.language_code[:2], '🏳️')
    header = (f"[{msg.from_user.first_name}](tg://user?id={msg.from_user.id}) "
              f"• до {expires} • 💰 ${donated:.2f} • {flag}")

    header_msg = await bot.send_message(CHAT_GROUP_ID, header, parse_mode='Markdown')
    relay[header_msg.message_id] = msg.from_user.id
    cp = await bot.copy_message(CHAT_GROUP_ID, msg.chat.id, msg.message_id)
    relay[cp.message_id] = msg.from_user.id


    

# ---------------- Group → user relay ----------------------
@dp.message(F.chat.id == CHAT_GROUP_ID)
async def relay_group(msg: Message):
    if (msg.reply_to_message and 
        msg.reply_to_message.message_id in relay):
        uid = relay[msg.reply_to_message.message_id]
        await bot.copy_message(uid, CHAT_GROUP_ID, msg.message_id)

# ---------------- Mount & run -----------------------------
dp.include_router(main_r)
dp.include_router(router)
dp.include_router(donate_r)

# ---------------- Webhook server (CryptoBot) --------------
from aiohttp import web

async def cryptobot_hook(request: web.Request):
    """Принимаем invoice_paid от CryptoBot и выдаём доступ"""
    data = await request.json()
    if data.get('update_type') != 'invoice_paid' or data.get('status') != 'paid':
        return web.json_response({'ok': True})

    payload_str = data.get('payload', '')
    try:
        uid_str, plan = payload_str.split(':', 1)
        user_id = int(uid_str)
    except ValueError:
        log.warning('[WEBHOOK] Bad payload: %s', payload_str)
        return web.json_response({'ok': False})

    await add_paid(user_id)  # +30 дней от текущего момента
    if plan == 'vip':
        await give_vip_channel(user_id)  # канал VIP

    # сохраняем сумму платежа
    asset = data.get('asset') or ''
    usd_amt = float(data.get('amount_usd') or 0)
    if not usd_amt and asset:
        try:
            rates = await exchange_rates()
            usd_amt = float(data.get('amount', 0)) * rates.get(asset.upper(), 0)
        except Exception:
            usd_amt = 0
    if usd_amt:
        await add_payment(user_id, usd_amt, asset)

    try:
        # determine user language
        try:
            chat=await bot.get_chat(user_id); lang=chat.language_code or 'ru'
        except Exception:
            lang='ru'
        await bot.send_message(user_id, tr(lang, 'pay_conf'))
    except Exception as e:
        log.warning('[WEBHOOK] Cannot notify user %s: %s', user_id, e)

    log.info('[WEBHOOK] Access granted user_id=%s plan=%s', user_id, plan)
    return web.json_response({'ok': True})

# ---------------- Run bot + aiohttp -----------------------
async def main():
    # aiohttp web‑server
    app = web.Application()
    app.router.add_post('/cryptobot/webhook', cryptobot_hook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    log.info('Webhook server started on 0.0.0.0:8080 /cryptobot/webhook')

    # aiogram polling
    log.info('JuicyFox Bot started')
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

