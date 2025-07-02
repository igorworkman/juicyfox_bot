# JuicyFox Bot — single‑file (aiogram 3.20) + 30‑day access
# ---------------------------------------------------------
# • Club / VIP / Chat  → 8 валют → счёт → доступ ровно 30 суток
# • Donate             → валюта → сумма (USD) → счёт
# • Relay              → приват ↔ группа (CHAT_GROUP_ID)
# • RU/EN UI           → auto by language_code

import os, logging, asyncio, httpx, time, aiosqlite
from typing import Dict, Any, Optional, Tuple
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ---------------- Config ----------------
TELEGRAM_TOKEN  = os.getenv('TELEGRAM_TOKEN')
CRYPTOBOT_TOKEN = os.getenv('CRYPTOBOT_TOKEN') or os.getenv('CRYPTO_BOT_TOKEN')
CHAT_GROUP_ID   = int(os.getenv('CHAT_GROUP_ID', '-1002813332213'))
LIVE_CHANNEL_URL= os.getenv('LIVE_CHANNEL_URL', 'https://t.me/JuisyFoxOfficialLife')
API_BASE        = 'https://pay.crypt.bot/api'
VIP_CHANNEL_ID  = int(os.getenv('VIP_CHANNEL_ID', '-1001234567890'))  # приватный VIP‑канал
DB_PATH         = 'juicyfox.db'

if not TELEGRAM_TOKEN or not CRYPTOBOT_TOKEN:
    raise RuntimeError('Set TELEGRAM_TOKEN and CRYPTOBOT_TOKEN env vars')

bot = Bot(TELEGRAM_TOKEN, parse_mode='HTML')
dp  = Dispatcher(storage=MemoryStorage())

# ---------------- Channel helpers ----------------
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
async def give_vip_channel(user_id:int):
    """Добавляем юзера в VIP канал или шлём инвайт"""
    try:
        await bot.add_chat_member(VIP_CHANNEL_ID, user_id)
    except TelegramForbiddenError:
        # бот не админ – пробуем разовую ссылку
        try:
            link = await bot.create_chat_invite_link(VIP_CHANNEL_ID, member_limit=1, expire_date=int(time.time())+3600)
            await bot.send_message(user_id, f'🔑 Ваш доступ к VIP каналу: {link.invite_link}')
        except TelegramBadRequest as e:
            log.warning('Cannot give VIP link: %s', e)

# ---------------- DB helpers -----------------
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS paid_users(
  user_id INTEGER PRIMARY KEY,
  expires INTEGER
);

CREATE TABLE IF NOT EXISTS payments(
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id  INTEGER,
  usd      REAL,
  asset    TEXT,
  ts       INTEGER
);
"""

async def _db_exec(q:str,*a):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_SQL)  # ensure both tables
        await db.execute(q,a)
        await db.commit()

async def add_paid(user_id:int, days:int=30):
    expires=int(time.time())+days*24*3600
    await _db_exec('INSERT OR REPLACE INTO paid_users VALUES(?,?)',user_id,expires)

async def is_paid(user_id:int)->bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_SQL)
        async with db.execute('SELECT expires FROM paid_users WHERE user_id=?',(user_id,)) as cur:
            row=await cur.fetchone(); return bool(row and row[0]>time.time())

async def add_payment(user_id:int, usd:float, asset:str):
    ts=int(time.time())
    await _db_exec('INSERT INTO payments(user_id,usd,asset,ts) VALUES(?,?,?,?)',user_id,usd,asset,ts)

async def total_donated(user_id:int)->float:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_SQL)
        async with db.execute('SELECT COALESCE(SUM(usd),0) FROM payments WHERE user_id=?',(user_id,)) as cur:
            row=await cur.fetchone(); return float(row[0] or 0)

async def expire_date_str(user_id:int)->str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT expires FROM paid_users WHERE user_id=?',(user_id,)) as cur:
            row=await cur.fetchone();
            if not row: return 'нет доступа'
            return time.strftime('%d.%m.%Y', time.localtime(row[0]))

# ---------------- i18n -------------------
L10N={
 'ru':{
  'menu': """Привет красавчик 😘 меня зовут Juicy Fox 🦊
У меня есть 2 ПРИВАТНЫХ канала которые сведут тебя с ума! 🔞💦🔥
А если хочешь поболтать со мной  — жми на кнопку Сhat...💬
💐И я отвечу тебе уже сегодня 💌""",
  'btn_live':'👀 Juicy live - 0 $',
  'btn_club':'💎 Luxury Room - 1 $',
  'btn_vip':'🖤 Secret VIP Club - 40 $',
  'btn_chat':'💬 Juicy Chat - 1 $',
  'btn_donate':'🎁 Custom',
  'choose_cur':'🧁 Готов побаловать меня? Выбери валюту 🛍️ ({amount}$)',
  'don_enter':'💸 Введи сумму в USD (5/10/25/50/100/200)',
  'don_num':'💸 Введи сумму доната в USD',
  'inv_err':'⚠️ Не удалось создать счёт. Попробуй другую валюту, милый 😉',
  'not_paid':'💬 Дорогой, активируй «Chat» и напиши мне снова. Я дождусь 😘',
  'live': """💎 Добро пожаловать в мой мир 💋
{live_link}""",
  'pay_conf':'✅ Всё получилось. Ты со мной на 30 дней 😘',
  'cancel':'❌ Тогда в другой раз…😔',
  'nothing_cancel':'Нечего отменять.'
 },
 'en':{
  'menu': """Hi, handsome 😘 My name is Juicy Fox 🦊
I have 2 PRIVATE channels that will drive you crazy! 🔞💦🔥
And if you want to chat with me — just tap the Chat button… 💬
💐 And I’ll reply to you today 💌""",
  'btn_live':'👀 Juicy live - 0 $',
  'btn_club':'💎 Luxury Room - 1 $',
  'btn_vip':'🖤 Secret VIP Club - 40 $',
  'btn_chat':'💬 Juicy Chat - 1 $',
  'btn_donate':'🎁 Custom',
  'choose_cur':'🧁 Ready to spoil me? Pick a currency 🛍️ ({amount}$)',
  'don_enter':'💸 Enter amount in USD (5/10/25/50/100/200)',
  'don_num':'💸 Enter a donation amount in USD',
  'inv_err':'⚠️ Failed to create invoice. Try another currency, sweetheart 😉',
  'not_paid':'💬 Darling, activate “Chat” and write me again. I’ll be waiting 😘',
  'live': """💎 Welcome to my world 💋
{live_link}""",
  'pay_conf':'✅ Done! You’re with me for 30 days 😘',
  'cancel':'❌ Maybe next time…😔',
  'nothing_cancel':'Nothing to cancel.',
  'back': '🔙 Back'
 }
}

def tr(code:Optional[str],key:str,**kw):
    lang='en' if code and code.startswith('en') else 'ru'
    return L10N[lang][key].format(**kw)

# ----- CryptoBot helpers -----
async def _api(m:str,ep:str,p:dict|None=None)->Optional[Dict[str,Any]]:
    hdr={'Crypto-Pay-API-Token':CRYPTOBOT_TOKEN}
    async with httpx.AsyncClient(timeout=10) as c:
        r=await c.request(m,f'{API_BASE}{ep}',json=p,headers=hdr); r.raise_for_status(); d=r.json()
        if d.get('ok'):return d['result']
        log.error('CryptoBot API error',extra={'ep':ep,'err':d.get('error'),'desc':d.get('description')});return None

async def exchange_rates()->Dict[str,float]:
    res=await _api('GET','/getExchangeRates') or []
    return {i['source'].upper():float(i['rate']) for i in res if i.get('is_crypto') and i.get('target')=='USD'}

async def create_invoice(uid:int,usd:float,asset:str,desc:str,pl:str|None=None)->Optional[str]:
    """Создаём счёт и прокидываем payload user_id:plan"""
    rates=await exchange_rates(); asset=asset.upper()
    if asset not in rates: return None
    amt=round(usd/rates[asset],6)
    payload_str=f"{uid}:{pl}" if pl else str(uid)
    body={
        'asset':asset,
        'amount':str(amt),
        'description':desc,
        'payload':payload_str,
        'paid_btn_name':'openBot',
        'paid_btn_url':f'https://t.me/{(await bot.get_me()).username}'
    }
    inv=await _api('POST','/createInvoice',body); return inv.get('pay_url') if inv else None

# ----- Data -----
relay: dict[int, int] = {}  # group_msg_id -> user_id
TARIFFS={'club':1.00,'vip':1.00,'chat':1.00}
CURRENCIES=[('TON','ton'),('BTC','btc'),('USDT','usdt'),('ETH','eth'),('BNB','bnb'),('TRX','trx'),('DAI','dai'),('USDC','usdc')]


router=Router(); donate_r=Router(); main_r=Router()

@router.callback_query(F.data.startswith('pay:'))
async def choose_cur(cq:CallbackQuery):
    plan=cq.data.split(':')[1]; amt=TARIFFS[plan]
    kb=InlineKeyboardBuilder();
    for t,c in CURRENCIES: kb.button(text=t,callback_data=f'payc:{plan}:{c}')
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    await cq.message.edit_text(tr(cq.from_user.language_code,'choose_cur',amount=amt),reply_markup=kb.as_markup())

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
    kb.button(text="⬅️ Назад", callback_data="back")
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
    kb.button(text="⬅️ Назад", callback_data="back")
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
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.button(text=tr(lang, 'btn_club'),   callback_data='pay:club')
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.button(text=tr(lang, 'btn_vip'),    callback_data='pay:vip')
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.button(text=tr(lang, 'btn_chat'),   callback_data='pay:chat')
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.button(text=tr(lang, 'btn_donate'), callback_data='donate')
    kb.button(text="⬅️ Назад", callback_data="back")
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
@router.callback_query(F.data == "back")
async def go_back_callback(cq: CallbackQuery):
    lang = cq.from_user.language_code
    await cq.message.edit_text(tr(lang, 'menu'), reply_markup=main_keyboard(lang))

def main_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=tr(lang, 'btn_live'),   callback_data='live')
    kb.button(text=tr(lang, 'btn_club'),   callback_data='pay:club')
    kb.button(text=tr(lang, 'btn_vip'),    callback_data='pay:vip')
    kb.button(text=tr(lang, 'btn_chat'),   callback_data='pay:chat')
    kb.button(text=tr(lang, 'btn_donate'), callback_data='donate')
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data == "back")
async def go_back_callback(cq: CallbackQuery):
    lang = cq.from_user.language_code
    await cq.message.edit_text(tr(lang, 'menu'), reply_markup=main_keyboard(lang))

def main_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=tr(lang, 'btn_live'),   callback_data='live')
    kb.button(text=tr(lang, 'btn_club'),   callback_data='pay:club')
    kb.button(text=tr(lang, 'btn_vip'),    callback_data='pay:vip')
    kb.button(text=tr(lang, 'btn_chat'),   callback_data='pay:chat')
    kb.button(text=tr(lang, 'btn_donate'), callback_data='donate')
    kb.adjust(1)
    return kb.as_markup()
