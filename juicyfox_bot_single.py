# JuicyFox Bot — single‑file (aiogram 3.20) + 30‑day access
# ---------------------------------------------------------
# • Club / VIP / Chat  → 8 валют → счёт → доступ ровно 30 суток
# • Donate             → валюта → сумма (USD) → счёт
# • Relay              → приват ↔ группа (CHAT_GROUP_ID)
# • RU/EN/ES UI           → auto by language_code

import os, logging, httpx, time, aiosqlite, traceback
import asyncio
import aiohttp
from os import getenv
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from datetime import datetime
DB_PATH = '/app/messages.sqlite'

os.makedirs('/data', exist_ok=True)

if not os.path.exists(DB_PATH):
    import sqlite3
    with sqlite3.connect(DB_PATH) as db:
        db.execute('CREATE TABLE IF NOT EXISTS messages (ts INTEGER, user_id INTEGER, msg_id INTEGER, is_reply INTEGER)')
from typing import Dict, Any, Optional, Tuple
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_post_plan_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="👀 Life", callback_data="post_to:life")
    kb.button(text="💿 Luxury", callback_data="post_to:luxury")
    kb.button(text="👑 VIP", callback_data="post_to:vip")
    kb.adjust(2)
    return kb.as_markup()

post_plan_kb = get_post_plan_kb()


from aiogram.fsm.state import StatesGroup, State
class Post(StatesGroup):
    wait_channel = State()
    wait_content = State()
    wait_confirm = State()

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

async def _init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS messages(
              ts INTEGER,
              user_id INTEGER,
              msg_id INTEGER,
              is_reply INTEGER
            );
        ''')
        await db.commit()


import os
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

# ---------------- Config ----------------
TELEGRAM_TOKEN  = os.getenv('TELEGRAM_TOKEN')
CRYPTOBOT_TOKEN = os.getenv('CRYPTOBOT_TOKEN') or os.getenv('CRYPTO_BOT_TOKEN')
CHAT_GROUP_ID = int(os.getenv("CHAT_GROUP_ID", "-1002813332213"))
HISTORY_GROUP_ID = -1002721298286
ADMINS = [7893194894]
LIFE_CHANNEL_ID = int(os.getenv("LIFE_CHANNEL_ID"))
LIFE_URL = os.getenv('LIFE_URL', 'https://t.me/JuisyFoxOfficialLife')
API_BASE        = 'https://pay.crypt.bot/api'
VIP_CHANNEL_ID  = int(os.getenv('VIP_CHANNEL_ID'))  # приватный VIP‑канал
log.debug(f"[DEBUG] VIP_CHANNEL_ID = {os.getenv('VIP_CHANNEL_ID')}")
LUXURY_CHANNEL_ID = int(os.getenv('LUXURY_CHANNEL_ID'))
POST_PLAN_GROUP_ID = int(os.getenv('POST_PLAN_GROUP_ID'))

CHANNELS = {
    "life": LIFE_CHANNEL_ID,
    "luxury": LUXURY_CHANNEL_ID,
    "vip": int(os.getenv("VIP_CHANNEL_ID")),
}

if not TELEGRAM_TOKEN or not CRYPTOBOT_TOKEN:
    raise RuntimeError('Set TELEGRAM_TOKEN and CRYPTOBOT_TOKEN env vars')

# --- Startup ------------------------------------------------
async def on_startup():
    print("DEBUG: on_startup called")
    asyncio.create_task(scheduled_poster())


bot = Bot(TELEGRAM_TOKEN, parse_mode='HTML')
dp  = Dispatcher(storage=MemoryStorage())
dp.startup.register(on_startup)


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

async def give_club_channel(user_id: int):
    try:
        await bot.add_chat_member(LUXURY_CHANNEL_ID, user_id)
    except TelegramForbiddenError:
        try:
            link = await bot.create_chat_invite_link(LUXURY_CHANNEL_ID, member_limit=1, expire_date=int(time.time())+3600)
            await bot.send_message(user_id, f'🔑 Доступ к Luxury Room: {link.invite_link}')
        except TelegramBadRequest as e:
            log.warning('Cannot give CLUB link: %s', e)

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
CREATE TABLE IF NOT EXISTS msg_count(
  user_id INTEGER PRIMARY KEY,
  cnt INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS messages(
  ts INTEGER,
  user_id INTEGER,
  msg_id INTEGER,
  is_reply INTEGER
);
CREATE TABLE IF NOT EXISTS scheduled_posts(
  created_ts INTEGER,
  publish_ts INTEGER,
  channel TEXT,
  price INTEGER,
  text TEXT,
  from_chat_id INTEGER,
  from_msg_id INTEGER,
  media_ids TEXT
);
CREATE TABLE IF NOT EXISTS published_posts(
  rowid INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER,
  message_id TEXT
);
"""

async def _db_exec(q: str, *a, fetchone: bool = False, fetchall: bool = False):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_SQL)  # ensure both tables
        cur = await db.execute(q, a)
        result = None
        if fetchone:
            result = await cur.fetchone()
        elif fetchall:
            result = await cur.fetchall()
        await db.commit()
        if fetchone or fetchall:
            return result

async def _db_fetchall(q:str,*a):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_SQL)
        return await db.execute_fetchall(q,a)

async def _db_fetchone(q:str, *a):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_SQL)
        return await db.execute_fetchone(q, a)

async def add_paid(user_id:int, days:int=30):
    expires=int(time.time())+days*24*3600
    await _db_exec('INSERT OR REPLACE INTO paid_users VALUES(?,?)',user_id,expires)

async def is_paid(user_id:int)->bool:
    if user_id == 7893194894:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_SQL)
        async with db.execute('SELECT expires FROM paid_users WHERE user_id=?',(user_id,)) as cur:
            row=await cur.fetchone(); return bool(row and row[0]>time.time())

async def is_paid_for(user_id: int, plan: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT expires FROM paid_users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return False
            if row[0] < time.time():
                return False
            return plan in ['vip', 'club']

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

# ----------- User message tracking -----------------
CONSECUTIVE_LIMIT = 3
COOLDOWN_SECS = 18 * 3600

async def inc_msg(uid: int) -> int:
    """Return how many messages in a row the user has sent including the current one."""
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_SQL)
        rows = await db.execute_fetchall(
            'SELECT ts, is_reply FROM messages WHERE user_id=? ORDER BY ts DESC LIMIT 10',
            (uid,)
        )

    cnt = 0
    for ts, is_reply in rows:
        if is_reply == 1 or now - ts > COOLDOWN_SECS:
            break
        cnt += 1

    return cnt + 1

async def reset_msg(uid:int):
    # Message history itself resets the counter. Kept for compatibility.
    return

# ---------------- i18n -------------------
L10N={
 'ru':{
  'menu': """Привет, {name} 😘 Я Juicy Fox 🦊
Мои 2 ПРИВАТНЫХ канала сведут тебя с ума! 🔞💦🔥
Хочешь поболтать со мной лично - открывай Juicy Сhat 💬💐
И я отвечу тебе уже сегодня 💌
Не забудь подписаться на мой бесплатный канал 👇🏼👇🏼👇🏼""",
  'btn_life':'👀 Juicy life - 0 $',
  'btn_club':'💎 Luxury Room - 15 $',
  'btn_vip':'❤️‍🔥 VIP Secret - 35 $',
  'btn_chat':'💬 Juicy Chat',
  'btn_donate':'🎁 Custom',
  'choose_cur':'🧁 Готов побаловать меня? Выбери валюту 🛍️ ({amount}$)',
  'don_enter':'💸 Введи сумму в USD (5/10/25/50/100/200)',
  'don_num':'💸 Введи сумму доната в USD',
 'inv_err':'⚠️ Не удалось создать счёт. Попробуй другую валюту, милый 😉',
 'not_paid':'💬 Дорогой, активируй «Chat» и напиши мне снова. Я дождусь 😘',
  'life': """💎 Добро пожаловать в мой мир 💋
{life_link}""",
  'pay_conf':'✅ Всё получилось. Ты со мной на 30 дней 😘',
  'cancel':'❌ Тогда в другой раз…😔',
  'nothing_cancel':'Нечего отменять.',
  'consecutive_limit': 'Вы не можете отправлять больше 3-х сообщений подряд, для продолжения переписки дождитесь ответа от Juicy Fox',
  'chat_flower_q': 'Какие цветы хотите подарить Juicy Fox?',
  'chat_flower_1': '🌷 — 5$ / 7 дней',
  'chat_flower_2': '🌹 — 9$ / 15 дней',
  'chat_flower_3': '💐 — 15$ / 30 дней',
  'chat_flower_desc': """💬 Juicy Chat — твоя личная связь с Juicy Fox 😘
Здесь начинается настоящий приват 💋
💌 Я отвечаю видео-кружками и голосовыми
📸 Иногда присылаю эксклюзивные селфи 😉
🤗 Я открою чат как только увижу твои цветы 💐🌷🌹""",
'desc_club': 'Luxury Room – Juicy Fox\n💎 Моя премиальная коллекция эротики создана для ценителей женской роскоши! 🔥 За символические 15 $ ты получишь контент без цензуры 24/7×30 дней 😈',
 'luxury_desc': 'Luxury Room – Juicy Fox\n💎 Моя премиальная коллекция эротики создана для ценителей женской роскоши! 🔥 За символические 15 $ ты получишь контент без цензуры на 30 дней😈',
 'vip_secret_desc': 'Твой личный доступ в VIP Secret от Juicy Fox 😈\n🔥Тут всё, о чём ты фантазировал:\n📸 больше HD фото нюдс крупным планом 🙈\n🎥 Видео, где я играю со своей киской 💦\n💬 Juicy Chat — где я отвечаю тебе лично, кружочками 😘\n📆 Период: 30 дней\n💸 Стоимость: 35,\n💳💵💱 — выбери, как тебе удобнее',
 'not_allowed_channel': '🚫 Неизвестный канал назначения.',
 'error_post_not_found': 'Пост не найден',
 'post_deleted':'Пост удалён',
},
 'en':{
  'menu': """Hey, {name} 😘 I’m your Juicy Fox tonight 🦊
My 2 PRIVATE channels will drive you wild… 🔞💦🔥
Just you and me… Ready for some late-night fun? 💋
Open Juicy Chat 💬 — and I’ll be waiting inside 💌
Don’t forget to follow my free channel 👇🏼👇🏼👇🏼""",
  'btn_life':'👀 Juicy life - 0 $',
  'btn_club':'💎 Luxury Room - 15 $',
  'btn_vip':'❤️‍🔥  VIP Secret - 35 $',
  'btn_chat':'💬 Juicy Chat',
  'btn_donate':'🎁 Custom',
  'choose_cur':'🧁 Ready to spoil me? Pick a currency 🛍️ ({amount}$)',
  'don_enter':'💸 Enter amount in USD (5/10/25/50/100/200)',
  'don_num':'💸 Enter a donation amount in USD',
  'inv_err':'⚠️ Failed to create invoice. Try another currency, sweetheart 😉',
  'not_paid':'💬 Darling, activate “Chat” and write me again. I’ll be waiting 😘',
  'life': """💎 Welcome to my world 💋
{life_link}""",
  'pay_conf':'✅ Done! You’re with me for 30 days 😘',
  'cancel':'❌ Maybe next time…😔',
  'nothing_cancel':'Nothing to cancel.',
  'consecutive_limit':'(3 of 3) — waiting for Juicy Fox\'s reply. You can continue in 18 hours or after she answers.',
  'chat_flower_q': 'What flowers would you like to gift Juicy Fox?',
  'chat_flower_1': '🌷 — $5 / 7 days',
  'chat_flower_2': '🌹 — $9 / 15 days',
  'chat_flower_3': '💐 — $15 / 30 days',
  'chat_flower_desc': """💬 Juicy Chat — your personal connection with Juicy Fox 😘
Just you and me... Let’s get a little closer 💋
💌 I love sending video rolls and voice replies
📸 I like sending private selfies... when you’ve been sweet 😉
🤗 I open the chat once I see your flowers 💐🌷🌹""",
  'back': '🔙 Back',
 'luxury_desc': 'Luxury Room – Juicy Fox\n💎 My premium erotica collection is made for connoisseurs of feminine luxury! 🔥 For just $15 you’ll get uncensored content for 30 days 😈',
'not_allowed_channel': '🚫 Unknown target channel.',
'error_post_not_found': 'Post not found',
'post_deleted':'Post deleted',
  "vip_secret_desc": "Your personal access to Juicy Fox’s VIP Secret 😈\n🔥 Everything you've been fantasizing about:\n📸 More HD Photo close-up nudes 🙈\n🎥 Videos where I play with my pussy 💦\n💬 Juicy Chat — where I reply to you personally, with video-rols 😘\n📆 Duration: 30 days\n💸 Price: $35\n💳💵💱 — choose your preferred payment method"
 },
'es': {
  'menu': """Hola, {name} 😘 Esta noche soy tu Juicy Fox 🦊
Mis 2 canales PRIVADOS te van a enloquecer… 🔞💦🔥
Solo tú y yo… ¿Listo para jugar esta noche? 💋
Haz clic en Juicy Chat 💬 — y te espero adentro 💌
No olvides suscribirte a mi canal gratis 👇🏼👇🏼👇🏼""",
  'btn_life': '👀 Juicy life - 0 $',
  'btn_club': '💎 Luxury Room - 15 $',
  'btn_vip': '❤️‍🔥 VIP Secret - 35 $',
  'btn_chat': '💬 Juicy Chat',
  'btn_donate': '🎁 Custom',
  'choose_cur': '🧁 ¿Listo para consentirme? Elige una moneda 🛍️ ({amount}$)',
  'don_enter': '💸 Introduce el monto en USD (5/10/25/50/100/200)',
  'don_num': '💸 Introduce una cantidad válida en USD',
  'inv_err': '⚠️ No se pudo crear la factura. Intenta con otra moneda, cariño 😉',
  'not_paid': '💬 Activa el “Chat” y vuelve a escribirme. Te estaré esperando 😘',
  'life': "💎 Bienvenido a mi mundo 💋\n{life_link}",
  'pay_conf': '✅ Todo listo. Estás conmigo durante 30 días 😘',
  'cancel': '❌ Quizás en otro momento… 😔',
  'nothing_cancel': 'No hay nada que cancelar.',
  'consecutive_limit': '(3 de 3) — esperando la respuesta de Juicy Fox. Podrás continuar la conversación en 18 horas o cuando responda.',
  'chat_flower_q': '¿Qué flores deseas regalar a Juicy Fox?',
  'chat_flower_1': '🌷 — $5 / 7 días',
  'chat_flower_2': '🌹 — $9 / 15 días',
  'chat_flower_3': '💐 — $15 / 30 días',
  'chat_flower_desc': """💬 Juicy Chat — tu conexión personal con Juicy Fox 😘
Solo tú y yo... Acércate un poquito más 💋
💌 Me encanta enviarte videomensajes y notas de voz
📸 Me gusta mandarte selfies privados... si te portas bien 😉
🤗 Abro el chat en cuanto vea tus flores 💐🌷🌹""",
  'back': '🔙 Back',
  'luxury_desc': 'Luxury Room – Juicy Fox\n💎 ¡Mi colección de erotismo premium está creada para los amantes del lujo femenino! 🔥 Por solo 15 $ obtendrás contenido sin censura 30 días 😈',
 'vip_secret_desc': "Tu acceso personal al VIP Secret de Juicy Fox 😈\n🔥 Todo lo que has estado fantaseando:\n📸 Más fotos HD de mis partes íntimas en primer plano 🙈\n🎥 Videos donde juego con mi Coño 💦\n💬 Juicy Chat — donde te respondo personalmente con videomensajes 😘\n📆 Duración: 30 días\n💸 Precio: 35$\n💳💵💱 — elige tu forma de pago preferida",
'not_allowed_channel': '🚫 Canal de destino desconocido.',
'error_post_not_found': 'Publicación no encontrada',
'post_deleted':'Post eliminado',
  }
}

def tr(code: Optional[str], key: str, **kw):
    lang = 'ru'  # fallback по умолчанию
    if code and code.startswith('en'):
        lang = 'en'
    elif code and code.startswith('es'):
        lang = 'es'
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
TARIFFS={'club':15.00,'vip':35.00}
CHAT_TIERS={7:5.0,15:9.0,30:15.0}
CURRENCIES=[('TON','ton'),('BTC','btc'),('USDT','usdt'),('ETH','eth'),('BNB','bnb'),('TRX','trx'),('DAI','dai'),('USDC','usdc')]


router=Router(); donate_r=Router(); main_r=Router()

@router.callback_query(F.data.startswith('pay:'))
async def choose_cur(cq: CallbackQuery, state: FSMContext):
    plan = cq.data.split(':')[1]
    if plan == 'chat':
        desc = tr(cq.from_user.language_code, 'chat_flower_desc')
        kb = InlineKeyboardBuilder()
        kb.button(text=tr(cq.from_user.language_code, 'chat_flower_1'), callback_data='chatgift:7')
        kb.button(text=tr(cq.from_user.language_code, 'chat_flower_2'), callback_data='chatgift:15')
        kb.button(text=tr(cq.from_user.language_code, 'chat_flower_3'), callback_data='chatgift:30')
        kb.button(text="⬅️ Назад", callback_data="back")
        kb.adjust(1)
        await cq.message.edit_text(desc, reply_markup=kb.as_markup())
        await state.set_state(ChatGift.choose_tier)
        return

    amt = TARIFFS[plan]
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f'payc:{plan}:{c}')
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    if plan == 'club':
        lang = cq.from_user.language_code
        text = L10N.get(lang, L10N['en'])['luxury_desc']
    elif plan in ('vip_secret', 'vip'):
        lang = cq.from_user.language_code
        text = L10N.get(lang, L10N['en'])['vip_secret_desc']
    else:
        text = tr(cq.from_user.language_code, 'choose_cur', amount=amt)
    await cq.message.edit_text(text, reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith('payc:'))
async def pay_make(cq: CallbackQuery):
    parts = cq.data.split(':')
    if len(parts) == 4 and parts[1] == 'chat':
        _, plan, days_str, cur = parts
        days = int(days_str)
        amt = CHAT_TIERS.get(days, 0)
        payload = f'chat_{days}'
    else:
        _, plan, cur = parts
        amt = TARIFFS[plan]
        payload = plan
    url = await create_invoice(cq.from_user.id, amt, cur, 'JuicyFox Subscription', pl=payload)
    if url:
        await cq.message.edit_text(f"Счёт на оплату ({plan.upper()}): {url}")
        
    else:
        await cq.answer(tr(cq.from_user.language_code,'inv_err'),show_alert=True)

# ---- Donate FSM ----
class Donate(StatesGroup):
    choosing_currency = State()
    entering_amount = State()

class ChatGift(StatesGroup):
    choose_tier = State()

@router.callback_query(F.data.startswith('chatgift:'), ChatGift.choose_tier)
async def chatgift_currency(cq: CallbackQuery, state: FSMContext):
    days = int(cq.data.split(':')[1])
    amt = CHAT_TIERS.get(days, 0)
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f'payc:chat:{days}:{c}')
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    await cq.message.edit_text(
        tr(cq.from_user.language_code, 'choose_cur', amount=amt),
        reply_markup=kb.as_markup(),
    )
    await state.clear()

@donate_r.callback_query(F.data == 'donate')
async def donate_currency(cq: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f'doncur:{c}')
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    await cq.message.edit_text(
        tr(cq.from_user.language_code, 'choose_cur', amount='donate'),
        reply_markup=kb.as_markup()
    )
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
    """Возврат к выбору валюты с кнопкой Назад"""
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
    kb.button(text=tr(lang, 'btn_life'),   callback_data='life')
    kb.button(text=tr(lang, 'btn_club'),   callback_data='pay:club')
    kb.button(text=tr(lang, 'btn_vip'),    callback_data='pay:vip')
    kb.button(text=tr(lang, 'btn_chat'),   callback_data='pay:chat')
    kb.button(text=tr(lang, 'btn_donate'), callback_data='donate')
    kb.adjust(1)
    await m.answer_photo("https://files.catbox.moe/cqckle.jpg")
    await m.answer(tr(lang, 'menu', name=m.from_user.first_name), reply_markup=kb.as_markup())

@main_r.callback_query(F.data == 'life')
async def life_link(cq: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(1)
    await cq.message.edit_text(
        tr(cq.from_user.language_code, 'life', life_link=LIFE_URL),
        reply_markup=kb.as_markup()
    )

@router.callback_query(F.data == 'back')
async def back_to_main(cq: CallbackQuery):
    lang = cq.from_user.language_code
    kb = InlineKeyboardBuilder()
    kb.button(text=tr(lang, 'btn_life'),   callback_data='life')
    kb.button(text=tr(lang, 'btn_club'),   callback_data='pay:club')
    kb.button(text=tr(lang, 'btn_vip'),    callback_data='pay:vip')
    kb.button(text=tr(lang, 'btn_chat'),   callback_data='pay:chat')
    kb.button(text=tr(lang, 'btn_donate'), callback_data='donate')
    kb.adjust(1)
    await cq.message.edit_text(
        tr(lang, 'menu', name=cq.from_user.first_name),
        reply_markup=kb.as_markup()
    )


# ---------------- Relay private ↔ group -------------------
@dp.message((F.chat.type == 'private') & (~F.text.startswith('/')))
async def relay_private(msg: Message):
    if not await is_paid(msg.from_user.id):
        await msg.reply(tr(msg.from_user.language_code, 'not_paid'))
        return

    cnt = await inc_msg(msg.from_user.id)
    if cnt > CONSECUTIVE_LIMIT:
        await msg.answer(tr(msg.from_user.language_code, 'consecutive_limit'))
        return

    # Формируем шапку
    expires = await expire_date_str(msg.from_user.id)
    donated = await total_donated(msg.from_user.id)
    flag = {
        'ru': '🇷🇺', 'en': '🇺🇸', 'tr': '🇹🇷', 'de': '🇩🇪'
    }.get(msg.from_user.language_code[:2], '🏳️')
    username = msg.from_user.full_name
    header = (f"{username} "
              f"• до {expires} • 💰 ${donated:.2f} • <code>{msg.from_user.id}</code> • {flag}")

    header_msg = await bot.send_message(CHAT_GROUP_ID, header, parse_mode="HTML")
    relay[header_msg.message_id] = msg.from_user.id

    cp = await bot.copy_message(CHAT_GROUP_ID, msg.chat.id, msg.message_id)
    relay[cp.message_id] = msg.from_user.id
    await _db_exec(
        'INSERT INTO messages VALUES(?,?,?,?)',
        int(time.time()),
        msg.from_user.id,
        cp.message_id,
        0,
    )


    

# ---------------- Group → user relay ----------------------
@dp.message(F.chat.id == CHAT_GROUP_ID)
async def relay_group(msg: Message):
    if (
        msg.reply_to_message
        and msg.reply_to_message.message_id in relay
        and msg.from_user.id in [a.user.id for a in await msg.chat.get_administrators()]
    ):
        uid = relay[msg.reply_to_message.message_id]
        cp = await bot.copy_message(uid, CHAT_GROUP_ID, msg.message_id)
        await _db_exec(
            'INSERT INTO messages VALUES(?,?,?,?)',
            int(time.time()),
            uid,
            cp.message_id,
            1,
        )

@dp.message(Command('history'))
async def history_request(msg: Message):
    if msg.chat.id != HISTORY_GROUP_ID or msg.from_user.id not in ADMINS:
        return

    args = msg.text.split()
    if len(args) < 2:
        await msg.reply("❌ Укажи user_id (и необязательно кол-во сообщений)")
        return

    try:
        uid = int(args[1])
        limit = int(args[2]) if len(args) > 2 else 10
    except ValueError:
        await msg.reply("❌ Неверный формат запроса.")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall(
            'SELECT ts, user_id, msg_id, is_reply FROM messages WHERE user_id=? ORDER BY ts DESC LIMIT ?',
            (uid, limit)
        )

    if not rows:
        await msg.reply("История пуста.")
        return

    await msg.reply(f"📂 История с user_id {uid} (последние {len(rows)} сообщений)")

    user = await bot.get_chat(uid)
    username = user.full_name or user.username or str(uid)

    for ts, user_id, msg_id, is_reply in reversed(rows):
        arrow_text = '⬅️' if is_reply else f'➡️ <b>{username}</b>'
        arrow_msg = await bot.send_message(HISTORY_GROUP_ID, arrow_text)
        try:
            cp = await bot.copy_message(HISTORY_GROUP_ID, CHAT_GROUP_ID, msg_id)
            if cp.text and '💰' in cp.text and '•' in cp.text:
                await bot.delete_message(HISTORY_GROUP_ID, cp.message_id)
                await bot.delete_message(HISTORY_GROUP_ID, arrow_msg.message_id)
        except Exception:
            await bot.send_message(HISTORY_GROUP_ID, 'Не удалось переслать сообщение')

@dp.message(Command("post"), F.chat.id == POST_PLAN_GROUP_ID)
async def cmd_post(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.reply("⛔️ Только админ может запускать постинг.")
        return
    await state.clear()
    await state.set_state(Post.wait_channel)
    await msg.answer("Куда постить?", reply_markup=post_plan_kb)


@dp.callback_query(F.data.startswith("post_to:"), Post.wait_channel)
async def post_choose_channel(cq: CallbackQuery, state: FSMContext):
    channel = cq.data.split(":")[1]
    await state.update_data(channel=channel, media_ids=[], text="")
    await state.set_state(Post.wait_content)
    kb = InlineKeyboardBuilder()
    kb.button(text="Готово", callback_data="post_done")
    kb.adjust(1)
    await cq.message.edit_text(
        f"Канал выбран: {channel}\n\nПришли текст поста или медиа.",
        reply_markup=kb.as_markup(),
    )


@dp.message(Post.wait_content, F.chat.id == POST_PLAN_GROUP_ID)
async def post_content(msg: Message, state: FSMContext):
    data = await state.get_data()
    channel = data.get("channel")
    if not channel:
        log.error("[POST_CONTENT] Channel not selected")
        await msg.reply("Ошибка: не выбран канал.")
        await state.clear()
        return
    if msg.photo or msg.video:
        ids = data.get("media_ids", [])
        file_id = msg.photo[-1].file_id if msg.photo else msg.video.file_id
        ids.append(file_id)
        await state.update_data(media_ids=ids)
        if msg.caption:
            await state.update_data(text=msg.caption)
        await msg.reply("Медиа добавлено")
    elif msg.text:
        await state.update_data(text=msg.text)
        await msg.reply("Текст сохранён")

@dp.callback_query(F.data == "post_done", Post.wait_content)
async def post_done(cq: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    channel = data.get("channel")
    media_ids = ','.join(data.get("media_ids", []))
    text = data.get("text", "")
    ts = int(time.time())
    await _db_exec(
        "INSERT INTO scheduled_posts VALUES(?,?,?,?,?,?,?,?)",
        int(time.time()),
        ts,
        channel,
        0,
        text,
        cq.message.chat.id,
        cq.message.message_id,
        media_ids,
    )
    await cq.message.edit_text("✅ Пост запланирован!")
    await state.clear()


@dp.message(F.chat.id == POST_PLAN_GROUP_ID)
async def handle_posting_plan(msg: Message):
    if msg.from_user.id not in ADMINS:
        await msg.reply("⛔️ Только админ может планировать посты.")
        return

    log.info(f"[DEBUG PLAN] msg.caption={msg.caption} | msg.text={msg.text}")
    text = msg.caption or msg.text
    if not text:
        return

    log.info(
        "[POSTING PLAN] Анализируем сообщение: %s от %s",
        msg.message_id,
        msg.chat.id,
    )

    lines = text.strip().split('\n')
    hashtags = {l.split('=')[0][1:]: l.split('=')[1] for l in lines if l.startswith('#') and '=' in l}
    description = '\n'.join(l for l in lines if not l.startswith('#'))

    target = hashtags.get("send_to")
    price = int(hashtags.get("price", 0))
    dt_str = hashtags.get("date")

    if target not in {"life", "luxury", "vip"}:
        log.warning(f"[POST PLAN] Unknown channel: {target}")
        await msg.reply("❌ Неизвестный канал назначения.")
        return

    if dt_str:
        try:
            ts = int(datetime.strptime(dt_str, "%Y-%m-%d %H:%M").timestamp())
        except Exception:
            log.warning("[POST PLAN] Bad date format: %s", dt_str)
            await msg.reply("❌ Неверный формат даты.")
            return
    else:
        ts = int(time.time())

    try:
        await _db_exec(
            "INSERT INTO scheduled_posts VALUES(?,?,?,?,?,?,?,?)",
            int(time.time()),
            ts,
            target,
            price,
            description,
            msg.chat.id,
            msg.message_id,
            "",
        )
        log.info(f"[DEBUG PLAN] Пост добавлен: {target} {dt_str} {description[:30]}")
        log.info(f"[SCHEDULED_POST] Added post: {target} text={(description or '<media>')[:40]} publish_ts={ts}")
    except Exception as e:
        log.error(f"[SCHEDULED_POST][FAIL] Could not add post: {e}"); await msg.reply("❌ Ошибка при добавлении поста."); return

    log.info("[POST PLAN] Scheduled post: #%s at %s (price=%s)", target, dt_str, price)
    await msg.reply("✅ Пост запланирован!")

# @dp.channel_post()
# async def debug_all_channel_posts(msg: Message):
#     log.info("[DEBUG] Got channel post in %s: %s", msg.chat.id, msg.text or "<media>")

async def scheduled_poster():
    print("DEBUG: scheduled_poster called!")
    log.info("[POSTING PLAN] Стартовал планировщик scheduled_poster")
    while True:
        await asyncio.sleep(10)
        now = int(time.time())
        log.debug(f"[DEBUG] Checking scheduled_posts, now={now}")

        rows = await _db_fetchall(
            "SELECT rowid, publish_ts, channel, price, text, from_chat_id, from_msg_id, media_ids FROM scheduled_posts WHERE publish_ts <= ?",
            now,
        )

        log.info(f"[DEBUG POSTER] найдено {len(rows)} пост(ов) к публикации")

        if not rows:
            log.debug("[SCHEDULED_POSTER] No posts scheduled for now.")

        for rowid, _, channel, price, text, from_chat, from_msg, media_ids in rows:
            chat_id = CHANNELS.get(channel)
            if not chat_id:
                log.warning(f"[SCHEDULED_POSTER] Channel {channel} not found in CHANNELS, skipping rowid={rowid}")
                continue
            log.debug(f"[DEBUG] Ready to post: rowid={rowid} channel={channel} text={text[:30]}")
            try:
                published = None
                sent_ids = []
                if media_ids:
                    ids = media_ids.split(',')
                    if len(ids) == 1:
                        file_id = ids[0]
                        if file_id.startswith("AgA"):
                            published = await bot.send_photo(chat_id, file_id, caption=text)
                        else:
                            published = await bot.send_video(chat_id, file_id, caption=text)
                        sent_ids.append(str(published.message_id))
                    else:
                        from aiogram.types import InputMediaPhoto, InputMediaVideo
                        media = []
                        for i, file_id in enumerate(ids):
                            if file_id.startswith("AgA"):
                                m = InputMediaPhoto(media=file_id, caption=text if i == 0 else None)
                            else:
                                m = InputMediaVideo(media=file_id, caption=text if i == 0 else None)
                            media.append(m)
                        grp = await bot.send_media_group(chat_id, media)
                        if grp:
                            published = grp[0]
                            sent_ids = [str(m.message_id) for m in grp]
                elif not media_ids and text:
                    # Если только текст — отправить текстовое сообщение
                    published = await bot.send_message(chat_id, text)
                    sent_ids.append(str(published.message_id))
                elif text == '<media>' or not text:
                    published = await bot.copy_message(chat_id, from_chat, from_msg)
                    sent_ids.append(str(published.message_id))
                else:
                    published = await bot.copy_message(chat_id, from_chat, from_msg, caption=text)
                    sent_ids.append(str(published.message_id))
                log.info(f"[POST OK] Message sent to {channel}")
                if published:
                    await _db_exec(
                        "INSERT INTO published_posts (chat_id, message_id) VALUES (?, ?)",
                        published.chat.id,
                        published.message_id,
                    )
            except TelegramBadRequest as e:
                log.warning(f"[POST FAIL] {e}")
                await _db_exec("DELETE FROM scheduled_posts WHERE rowid=?", rowid)
                continue
            except Exception as e:
                log.error(f"[FATAL POST FAIL] {e}\n{traceback.format_exc()}")
                continue
            await asyncio.sleep(0.2)
            await _db_exec("DELETE FROM scheduled_posts WHERE rowid=?", rowid)
            if published:
                await bot.send_message(
                    POST_PLAN_GROUP_ID,
                    f"✅ Пост опубликован! Для удаления: /delete_post {published.message_id}",
                )

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

    days = 30
    if plan.startswith('chat_'):
        days = int(plan.split('_')[1])
    await add_paid(user_id, days)
    if plan == 'club':
        await give_club_channel(user_id)
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
    print("DEBUG: Inside main()")
    # aiohttp web‑server
    app = web.Application()
    app.router.add_post('/cryptobot/webhook', cryptobot_hook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    # отключён запуск aiohttp-сервера во избежание конфликта портов
    pass

    # aiogram polling
    log.info('JuicyFox Bot started')
    await dp.start_polling(bot)

@dp.message(Command("test_vip"))
async def test_vip_post(msg: Message):
    if msg.from_user.id not in ADMINS:
        await msg.reply("⛔️ Нет доступа.")
        return
    try:
        await bot.send_message(CHANNELS["vip"], "✅ Проверка: бот может писать в VIP")
        await msg.reply("✅ Успешно отправлено в VIP-канал")
    except Exception as e:
        await msg.reply(f"❌ Ошибка при отправке в VIP: {e}")

@dp.message(Command("delete_post"))
async def delete_post_cmd(msg: Message):
    lang = msg.from_user.language_code
    if msg.from_user.id not in ADMINS:
        await msg.reply("⛔️ Только админ может удалять посты.")
        return

    parts = msg.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await msg.reply("❌ Используй /delete_post <id>")
        return

    msg_id = int(parts[1])
    row = await _db_exec(
        "SELECT chat_id FROM published_posts WHERE message_id = ?",
        (msg_id,),
        fetchone=True,
    )
    if not row:
        await msg.reply(tr(lang, 'error_post_not_found'))
        return
    chat_id = row[0]
    if chat_id not in [VIP_CHANNEL_ID, LIFE_CHANNEL_ID, LUXURY_CHANNEL_ID]:
        await msg.reply(tr(lang, 'not_allowed_channel'))
        return
    try:
        await bot.delete_message(chat_id, msg_id)
        await msg.reply(tr(lang, 'post_deleted'))
    except Exception as e:
        await msg.reply(f"❌ Ошибка удаления: {e}")

async def setup_webhook():
    session = AiohttpSession()
    bot = Bot(token=getenv("TELEGRAM_TOKEN"), session=session)
    webhook_url = getenv("WEBHOOK_URL")
    await bot.set_webhook(webhook_url)

if __name__ == '__main__':
    # Avoid starting an extra aiohttp server when running under gunicorn
    if "gunicorn" not in os.getenv("SERVER_SOFTWARE", "").lower():
        asyncio.run(setup_webhook())
        print("DEBUG: JuicyFox main() will run")
        asyncio.run(main())

