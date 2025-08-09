# JuicyFox Bot — single‑file (aiogram 3.20) + 30‑day access
# ---------------------------------------------------------
# • Club / VIP / Chat  → 8 валют → счёт → доступ ровно 30 суток
# • Donate             → валюта → сумма (USD) → счёт
# • Relay              → приват ↔ группа (CHAT_GROUP_ID)
# • RU/EN/ES UI           → auto by language_code

import os, logging, httpx, time, aiosqlite, traceback, sqlite3
from pathlib import Path
import asyncio
import aiohttp
from os import getenv
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from datetime import datetime
from types import SimpleNamespace
os.makedirs("data", exist_ok=True)
DB_PATH = Path(__file__).parent / "data" / "messages.db"

if not os.path.exists(DB_PATH):
    with sqlite3.connect(DB_PATH) as db:
        db.execute('CREATE TABLE IF NOT EXISTS messages (uid INTEGER, sender TEXT, text TEXT, file_id TEXT, media_type TEXT, timestamp INTEGER)')

def migrate_add_ts_column():
    pass

from typing import Dict, Any, Optional, Tuple, List
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_post_plan_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="👀 Life", callback_data="post_to:life")
    kb.button(text="💿 Luxury", callback_data="post_to:luxury")
    kb.button(text="👑 VIP", callback_data="post_to:vip")
    kb.adjust(1)
    return kb.as_markup()

post_plan_kb = get_post_plan_kb()

# ==============================
#  POSTING GROUP — обновлённая версия
# ==============================

POST_PLAN_GROUP_ID = -1002825908735
POST_PLAN_GROUP_ID = int(POST_PLAN_GROUP_ID)
POST_COUNTER = 1

def chat_plan_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key, days in [('chat_flower_1',7), ('chat_flower_2',15), ('chat_flower_3',30)]:
        kb.button(text=tr(lang, key), callback_data=f'chatgift:{days}')
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(1)
    return kb.as_markup()

def build_tip_menu(lang: str) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text=tr(lang, 'btn_life'), callback_data='life')
    kb.button(text=tr(lang, 'btn_club'), callback_data='pay:club')
    kb.button(text=tr(lang, 'btn_vip'), callback_data='pay:vip')
    kb.button(text=tr(lang, 'btn_donate'), callback_data='donate')
    kb.button(text="💬 Chat", callback_data='pay:chat')
    kb.adjust(1)
    return kb


from aiogram.fsm.state import StatesGroup, State
class Post(StatesGroup):
    wait_channel = State()
    wait_content = State()
    wait_confirm = State()

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey

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
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/runtime.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)
logging.info("\ud83d\udd25 Bot launched successfully")


def relay_error_handler(func):
    async def wrapper(msg: Message, *a, **kw):
        try:
            return await func(msg, *a, **kw)
        except Exception as e:
            log.exception("%s error: %s", func.__name__, e)
    return wrapper


def extract_media(msg: Message):
    text = msg.text or msg.caption or ''
    fid = mtype = None
    if msg.photo:
        fid, mtype = msg.photo[-1].file_id, 'photo'
    elif msg.voice:
        fid, mtype = msg.voice.file_id, 'voice'
    elif msg.video:
        fid, mtype = msg.video.file_id, 'video'
    elif msg.animation:
        fid, mtype = msg.animation.file_id, 'animation'
    elif msg.video_note:
        fid, mtype = msg.video_note.file_id, 'video_note'
    return text, fid, mtype


async def send_to_history(bot, chat_id, msg):
    sender = getattr(msg, "sender", "user")
    text = (msg.caption or msg.text or "").strip()
    if sender == "admin":
        caption = f"📩 Ответ от оператора\n{text}" if text else "📩 Ответ от оператора"
    else:
        caption = text

    try:
        if getattr(msg, "photo", None):
            await bot.send_photo(chat_id, msg.photo[-1].file_id, caption=caption)
        elif getattr(msg, "voice", None):
            await bot.send_voice(chat_id, msg.voice.file_id, caption=caption)
        elif getattr(msg, "video", None):
            await bot.send_video(chat_id, msg.video.file_id, caption=caption)
        elif getattr(msg, "animation", None):
            await bot.send_animation(chat_id, msg.animation.file_id, caption=caption)
        elif getattr(msg, "video_note", None):
            await bot.send_video_note(chat_id, msg.video_note.file_id)
            if caption:
                await bot.send_message(chat_id, caption)
        elif caption:
            await bot.send_message(chat_id, caption)
        else:
            await bot.send_message(chat_id, "📩 Ответ от оператора (без текста)")
    except Exception as e:
        log.error("[ERROR] Не удалось отправить в историю: %s", e)


async def get_last_messages(uid: int, limit: int):
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall(
            "SELECT sender, text, file_id, media_type FROM messages WHERE uid = ? ORDER BY timestamp DESC LIMIT ?",
            (uid, limit),
        )

    messages = []
    for sender, text, fid, mtype in reversed(rows):
        msg = SimpleNamespace(sender=sender, text=None, caption=None, photo=None, voice=None, video=None, animation=None, video_note=None)
        if mtype == "photo":
            msg.caption = text
            msg.photo = [SimpleNamespace(file_id=fid)]
        elif mtype == "voice":
            msg.caption = text
            msg.voice = SimpleNamespace(file_id=fid)
        elif mtype == "video":
            msg.caption = text
            msg.video = SimpleNamespace(file_id=fid)
        elif mtype == "animation":
            msg.caption = text
            msg.animation = SimpleNamespace(file_id=fid)
        elif mtype == "video_note":
            msg.video_note = SimpleNamespace(file_id=fid)
        else:
            msg.text = text
        messages.append(msg)
    return messages

# ---------------- Config ----------------
TELEGRAM_TOKEN  = os.getenv('TELEGRAM_TOKEN')
CRYPTOBOT_TOKEN = os.getenv('CRYPTOBOT_TOKEN') or os.getenv('CRYPTO_BOT_TOKEN')

# --- Codex-hack: TEMPORARY DISABLE env checks for Codex PR ---
# if not TELEGRAM_TOKEN or not CRYPTOBOT_TOKEN:
#     raise RuntimeError('Set TELEGRAM_TOKEN and CRYPTOBOT_TOKEN env vars')
# --- END Codex-hack ---

CHAT_GROUP_ID = int(os.getenv("CHAT_GROUP_ID", "-1002813332213"))
# Cast HISTORY_GROUP_ID to int so numeric chat IDs match correctly
HISTORY_GROUP_ID = int(getenv("HISTORY_GROUP_ID"))
ADMINS = [7893194894]
LIFE_CHANNEL_ID = int(os.getenv("LIFE_CHANNEL_ID"))
LIFE_URL = os.getenv('LIFE_URL', 'https://t.me/JuisyFoxOfficialLife')
API_BASE        = 'https://pay.crypt.bot/api'
VIP_URL = os.getenv("VIP_URL")

CHANNELS = {
    "life": LIFE_CHANNEL_ID,
    "luxury": int(os.getenv("LUXURY_CHANNEL_ID")),
    "vip": int(os.getenv("VIP_CHANNEL_ID")),
    "chat_30": CHAT_GROUP_ID,  # Juicy Chat group
}

log.info(
    "Env CHAT_GROUP_ID=%s HISTORY_GROUP_ID=%s LIFE_CHANNEL_ID=%s POST_PLAN_GROUP_ID=%s",
    CHAT_GROUP_ID,
    HISTORY_GROUP_ID,
    LIFE_CHANNEL_ID,
    POST_PLAN_GROUP_ID,
)

if not TELEGRAM_TOKEN or not CRYPTOBOT_TOKEN:
    raise RuntimeError('Set TELEGRAM_TOKEN and CRYPTOBOT_TOKEN env vars')

# --- Startup ------------------------------------------------
async def on_startup():
    log.debug("on_startup called")
    await _db_exec(
        "CREATE TABLE IF NOT EXISTS reply_links (reply_msg_id INTEGER PRIMARY KEY, user_id INTEGER)"
    )
    asyncio.create_task(scheduled_poster())


bot = Bot(token=TELEGRAM_TOKEN, parse_mode='HTML')
dp  = Dispatcher(storage=MemoryStorage())
dp.startup.register(on_startup)


# ---------------- Channel helpers ----------------
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
async def give_vip_channel(user_id:int):
    """Добавляем юзера в VIP канал или шлём инвайт"""
    try:
        await bot.add_chat_member(CHANNELS["vip"], user_id)
    except TelegramForbiddenError:
        # бот не админ – пробуем разовую ссылку
        try:
            link = await bot.create_chat_invite_link(CHANNELS["vip"], member_limit=1, expire_date=int(time.time())+3600)
            await bot.send_message(user_id, f'🔑 Ваш доступ к VIP каналу: {link.invite_link}')
        except TelegramBadRequest as e:
            log.warning('Cannot give VIP link: %s', e)

async def give_club_channel(user_id: int):
    try:
        await bot.add_chat_member(CHANNELS["luxury"], user_id)
    except TelegramForbiddenError:
        try:
            link = await bot.create_chat_invite_link(CHANNELS["luxury"], member_limit=1, expire_date=int(time.time())+3600)
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
CREATE TABLE IF NOT EXISTS reply_links(
  reply_msg_id INTEGER PRIMARY KEY,
  user_id INTEGER
);
CREATE TABLE IF NOT EXISTS scheduled_posts(
  created_ts INTEGER,
  publish_ts INTEGER,
  channel TEXT,
  price INTEGER,
  text TEXT,
  from_chat_id INTEGER,
  from_msg_id INTEGER,
  media_ids TEXT,
  status TEXT DEFAULT 'scheduled',
  is_sent INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS published_posts(
  rowid INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER,
  message_id TEXT
);
"""

async def _db_exec(
    q: str,
    *a,
    fetchone: bool = False,
    fetchall: bool = False,
    return_rowid: bool = False,
    return_rowcount: bool = False,
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_SQL)  # ensure both tables
        cur = await db.execute(q, a)
        result = None
        if fetchone:
            result = await cur.fetchone()
        elif fetchall:
            result = await cur.fetchall()
        elif return_rowid:
            result = cur.lastrowid
        elif return_rowcount:
            result = cur.rowcount
        await db.commit()
        if fetchone or fetchall or return_rowid or return_rowcount:
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
COOLDOWN_SECS = 600

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
  'tip_menu': '🛍 Tip Menu',
  'activate_chat':'See you my chaT 💬', 'life_link':'👀 Мой канал: {url}', 'my_channel': '👀 Мой бесплатный канал: {link}',
  'choose_action': 'Выбери действие ниже:',
  'choose_cur':'🧁 Готов побаловать меня? Выбери валюту 🛍️ ({amount}$)',
  'don_enter':'💸 Введи сумму в USD (5/10/25/50/100/200)',
  'don_num':'💸 Введи сумму доната в USD',
 'inv_err':'⚠️ Не удалось создать счёт. Попробуй другую валюту, милый 😉',
 'not_paid':'💬 Дорогой, активируй «Chat» и напиши мне снова. Я дождусь 😘',
  'life': """💎 Добро пожаловать в мой мир 💋
{my_channel}""",
  'pay_conf':'✅ Всё получилось. Ты со мной на 30 дней 😘',
  'cancel':'❌ Тогда в другой раз…😔',
  'nothing_cancel':'Нечего отменять.',
  'consecutive_limit': 'Вы не можете отправлять больше 3-х сообщений подряд, подождите 10 минут или дождитесь ответа от Juicy Fox',
  'chat_choose_plan': '💬 На сколько дней активировать чат?',
  'chat_flower_q': 'Какие цветы хотите подарить Juicy Fox?',
  'chat_flower_1': '🌷 — 5$ / 7 дней',
  'chat_flower_2': '🌹 — 9$ / 15 дней',
  'chat_flower_3': '💐 — 15$ / 30 дней',
  'chat_flower_desc': """💬 Juicy Chat — твоя личная связь с Juicy Fox 😘
Здесь начинается настоящий приват 💋
💌 Я отвечаю видео-кружками и голосовыми
📸 Иногда присылаю эксклюзивные селфи 😉
🤗 Я открою чат как только увижу твои цветы 💐🌷🌹""",
  'chat_access': (
    "Доступ в Chat 💬 — это твоя личная связь с Juicy Fox 😘\n"
    "Здесь начинается настоящий Private 💋\n"
    "Часто отвечаю видео-кружками и голосовыми 💌\n"
    "Иногда присылаю эксклюзивные селфи 📸😉\n"
    "НО… без цветов 💐 — не пущу тебя! 😜☺️"
  ),
'desc_club': 'Luxury Room – Juicy Fox\n💎 Моя премиальная коллекция эротики создана для ценителей женской роскоши! 🔥 За символические 15 $ ты получишь контент без цензуры 24/7×30 дней 😈',
 'luxury_room_desc': 'Luxury Room – Juicy Fox\n💎 Моя премиальная коллекция эротики создана для ценителей женской роскоши! 🔥 За символические 15 $ ты получишь контент без цензуры на 30 дней😈',
 'vip_secret_desc': (
    "Твой личный доступ в VIP Secret от Juicy Fox 😈\n"
    "🔥Тут всё, о чём ты фантазировал:\n"
    "📸 больше HD фото нюдс крупным планом 🙈\n"
    "🎥 Видео, где я играю со своей киской 💦\n"
    "💬 Juicy Chat — где я отвечаю тебе лично, кружочками 😘\n"
    "📅 Период: 30 дней\n"
    "💵 Стоимость: 35,\n"
    "💳💸 — выбери, как тебе удобнее"
 ),
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
  'tip_menu': '🛍 Tip Menu',
  'activate_chat':'See you my chaT 💬', 'life_link':'👀 My channel: {url}', 'my_channel': '👀 My free channel: {link}',
  'choose_action': 'Choose an action below:',
  'choose_cur':'🧁 Ready to spoil me? Pick a currency 🛍️ ({amount}$)',
  'don_enter':'💸 Enter amount in USD (5/10/25/50/100/200)',
  'don_num':'💸 Enter a donation amount in USD',
  'inv_err':'⚠️ Failed to create invoice. Try another currency, sweetheart 😉',
  'not_paid':'💬 Darling, activate “Chat” and write me again. I’ll be waiting 😘',
  'life': """💎 Welcome to my world 💋
{my_channel}""",
  'pay_conf':'✅ Done! You’re with me for 30 days 😘',
  'cancel':'❌ Maybe next time…😔',
  'nothing_cancel':'Nothing to cancel.',
  'consecutive_limit':'(3 of 3) — waiting for Juicy Fox\'s reply. You can continue in 10 minutes or after she answers.',
  'chat_choose_plan': '💬 Choose chat duration',
  'chat_flower_q': 'What flowers would you like to gift Juicy Fox?',
  'chat_flower_1': '🌷 — $5 / 7 days',
  'chat_flower_2': '🌹 — $9 / 15 days',
  'chat_flower_3': '💐 — $15 / 30 days',
  'chat_flower_desc': """💬 Juicy Chat — your personal connection with Juicy Fox 😘
Just you and me... Let’s get a little closer 💋
💌 I love sending video rolls and voice replies
📸 I like sending private selfies... when you’ve been sweet 😉
🤗 I open the chat once I see your flowers 💐🌷🌹""",
  'chat_access': (
    "Access to Chat 💬 is your personal connection with Juicy Fox 😘\n"
    "This is where the real Private 💋 begins\n"
    "I often reply with video messages and voice notes 💌\n"
    "Sometimes I send you exclusive selfies 📸😉\n"
    "BUT… no flowers 💐 — no entry! 😜☺️"
  ),
  'back': '🔙 Back',
 'luxury_room_desc': 'Luxury Room – Juicy Fox\n💎 My premium erotica collection is made for connoisseurs of feminine luxury! 🔥 For just $15 you’ll get uncensored content for 30 days 😈',
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
  'tip_menu': '🛍 Tip Menu',
  'activate_chat':'See you my chaT 💬', 'life_link':'👀 Mi canal: {url}', 'my_channel': '👀 Mi canal gratuito: {link}',
  'choose_action': 'Elige una acción abajo:',
  'choose_cur': '🧁 ¿Listo para consentirme? Elige una moneda 🛍️ ({amount}$)',
  'don_enter': '💸 Introduce el monto en USD (5/10/25/50/100/200)',
  'don_num': '💸 Introduce una cantidad válida en USD',
  'inv_err': '⚠️ No se pudo crear la factura. Intenta con otra moneda, cariño 😉',
  'not_paid': '💬 Activa el “Chat” y vuelve a escribirme. Te estaré esperando 😘',
  'life': "💎 Bienvenido a mi mundo 💋\n{my_channel}",
  'pay_conf': '✅ Todo listo. Estás conmigo durante 30 días 😘',
  'cancel': '❌ Quizás en otro momento… 😔',
  'nothing_cancel': 'No hay nada que cancelar.',
  'consecutive_limit': '(3 de 3) — esperando la respuesta de Juicy Fox. Podrás continuar la conversación en 10 minutos o cuando responda.',
  'chat_choose_plan': '💬 ¿Por cuántos días activar el chat?',
  'chat_flower_q': '¿Qué flores deseas regalar a Juicy Fox?',
  'chat_flower_1': '🌷 — $5 / 7 días',
  'chat_flower_2': '🌹 — $9 / 15 días',
  'chat_flower_3': '💐 — $15 / 30 días',
  'chat_flower_desc': """💬 Juicy Chat — tu conexión personal con Juicy Fox 😘
Solo tú y yo... Acércate un poquito más 💋
💌 Me encanta enviarte videomensajes y notas de voz
📸 Me gusta mandarte selfies privados... si te portas bien 😉
🤗 Abro el chat en cuanto vea tus flores 💐🌷🌹""",
  'chat_access': (
    "El acceso al Chat 💬 es tu conexión personal con Juicy Fox 😘\n"
    "Aquí empieza lo verdaderamente Privado 💋\n"
    "A menudo respondo con videomensajes y audios 💌\n"
    "A veces te mando selfies exclusivos 📸😉\n"
    "PERO… ¡sin flores 💐 no entras! 😜☺️"
  ),
  'back': '🔙 Back',
  'luxury_room_desc': 'Luxury Room – Juicy Fox\n💎 ¡Mi colección de erotismo premium está creada para los amantes del lujo femenino! 🔥 Por solo 15 $ obtendrás contenido sin censura 30 días 😈',
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

def vip_currency_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f'vipay:{c}')
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    return kb.as_markup()


router=Router(); donate_r=Router(); main_r=Router()


@router.callback_query(F.data.startswith('pay:'))
async def choose_cur(cq: CallbackQuery, state: FSMContext):
    plan = cq.data.split(':')[1]
    lang = cq.from_user.language_code
    if plan == 'chat':
        await cq.message.edit_text(
            tr(lang, 'chat_access'),
            reply_markup=chat_plan_kb(lang)
        )
        await state.set_state(ChatGift.choose_tier)
        return

    if plan in ('vip_secret', 'vip'):
        await cq.message.edit_text(
            tr(lang, 'vip_secret_desc'),
            reply_markup=vip_currency_kb()
        )
        return

    amt = TARIFFS[plan]
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f'payc:{plan}:{c}')
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    if plan == 'club':
        text = L10N.get(lang, L10N['en'])['luxury_room_desc']
    else:
        text = tr(lang, 'choose_cur', amount=amt)
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

@router.callback_query(F.data.startswith('vipay:'))
async def handle_vip_currency(cq: CallbackQuery):
    cur = cq.data.split(':')[1]
    amt = TARIFFS['vip']
    url = await create_invoice(cq.from_user.id, amt, cur, 'JuicyFox Subscription', pl='vip')
    if url:
        await cq.message.edit_text(f"Счёт на оплату (VIP): {url}")
    else:
        await cq.answer(tr(cq.from_user.language_code,'inv_err'), show_alert=True)

# ---- Donate FSM ----
class Donate(StatesGroup):
    choosing_currency = State()
    entering_amount = State()

class ChatGift(StatesGroup):
    plan = State()
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
    reply_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="SEE YOU MY CHAT💬")],
            [
                KeyboardButton(text="💎 Luxury Room - 15$"),
                KeyboardButton(text="❤️‍🔥 VIP Secret - 35$")
            ]
        ],
        resize_keyboard=True
    )

    kb = build_tip_menu(lang)

    await m.answer_photo(
        photo="https://files.catbox.moe/cqckle.jpg",
        caption=tr(lang, 'menu', name=m.from_user.first_name),
    )


    await m.answer(
        text=tr(lang, 'my_channel', link=LIFE_URL),
        reply_markup=reply_kb
    )

@main_r.callback_query(F.data == 'life')
async def life_link(cq: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(1)
    await cq.message.edit_text(
        tr(cq.from_user.language_code, 'life', my_channel=LIFE_URL),
        reply_markup=kb.as_markup()
    )

@router.callback_query(F.data == 'back')
async def back_to_main(cq: CallbackQuery):
    lang = cq.from_user.language_code
    kb = build_tip_menu(lang)
    await cq.message.edit_text(
        tr(lang, 'choose_action'),
        reply_markup=kb.as_markup()
    )

@main_r.callback_query(F.data == 'tip_menu')
async def tip_menu(cq: CallbackQuery):
    lang = cq.from_user.language_code
    kb = build_tip_menu(lang)
    await cq.message.answer(tr(lang, 'choose_action'), reply_markup=kb.as_markup())


@dp.message(lambda msg: msg.text == "SEE YOU MY CHAT💬")
async def handle_chat_btn(msg: Message, state: FSMContext):
    lang = msg.from_user.language_code
    await state.set_state(ChatGift.plan)
    await msg.answer(
        tr(lang, 'chat_access'),
        reply_markup=chat_plan_kb(lang)
    )




@dp.message(lambda msg: msg.text == "💎 Luxury Room - 15$")
async def luxury_room_reply(msg: Message):
    lang = msg.from_user.language_code
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f'payc:club:{c}')
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    await msg.answer(tr(lang, 'luxury_room_desc'), reply_markup=kb.as_markup())
@dp.message(lambda msg: msg.text == "❤️‍🔥 VIP Secret - 35$")
async def vip_secret_reply(msg: Message):
    lang = msg.from_user.language_code
    await msg.answer(
        tr(lang, 'vip_secret_desc'),
        reply_markup=vip_currency_kb()
    )





# ---------------- Relay private ↔ group -------------------
@dp.message((F.chat.type == 'private') & (~F.text.startswith('/')))
@relay_error_handler
async def relay_private(msg: Message, state: FSMContext, **kwargs):
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

    header_msg = await bot.send_message(CHANNELS["chat_30"], header, parse_mode="HTML")
    relay[header_msg.message_id] = msg.from_user.id

    cp = await bot.copy_message(CHANNELS["chat_30"], msg.chat.id, msg.message_id)
    relay[cp.message_id] = msg.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO reply_links (reply_msg_id, user_id) VALUES (?, ?)",
            (header_msg.message_id, msg.from_user.id),
        )
        await db.execute(
            "INSERT OR REPLACE INTO reply_links (reply_msg_id, user_id) VALUES (?, ?)",
            (cp.message_id, msg.from_user.id),
        )
        text, fid, mtype = extract_media(msg)
        await db.execute(
            "INSERT INTO messages (uid, sender, text, file_id, media_type, timestamp) VALUES (?,?,?,?,?,?)",
            (msg.from_user.id, 'user', text, fid, mtype, int(time.time())),
        )
        await db.commit()


    

# ---------------- Group → user relay ----------------------
@dp.message(F.chat.id == CHANNELS["chat_30"])
@relay_error_handler
async def relay_group(msg: Message, state: FSMContext, **kwargs):
    if not msg.reply_to_message:
        return
    uid = relay.get(msg.reply_to_message.message_id)
    if uid is None:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_id FROM reply_links WHERE reply_msg_id = ?",
                (msg.reply_to_message.message_id,),
            )
            row = await cursor.fetchone()
            if row:
                uid = row[0]
    if uid and msg.from_user.id in [a.user.id for a in await msg.chat.get_administrators()]:
        await bot.copy_message(uid, CHANNELS["chat_30"], msg.message_id)
        # await send_to_history(bot, HISTORY_GROUP_ID, msg)

        text, file_id, media_type = extract_media(msg)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (uid, sender, text, file_id, media_type, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, 'admin', text, file_id, media_type, int(time.time())),
        )
        await db.commit()

# legacy history handler
async def _unused_cmd_history_2(msg: Message):
    log.debug("Received /history in chat=%s text=%s", msg.chat.id, msg.text)
    if msg.chat.id != HISTORY_GROUP_ID:
        log.error("/history used outside history group: chat_id=%s", msg.chat.id)
        await msg.reply("Команда доступна только в чате истории")
        return

    args = msg.text.split()
    if len(args) != 3:
        log.error("/history invalid args count: %s", msg.text)
        await msg.reply("неверный синтаксис")
        return

    try:
        uid = int(args[1])
        limit = int(args[2])
    except ValueError:
        log.error("/history invalid uid/limit: %s", msg.text)
        await msg.reply("неверный синтаксис")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall(
            'SELECT sender, text, file_id, media_type FROM messages WHERE uid = ? ORDER BY timestamp DESC LIMIT ?',
            (uid, limit)
        )

    if not rows:
        await msg.reply("Нет сообщений")
        return

    for sender, text, file_id, media_type in rows:
        caption = text if sender == 'user' else f"📬 Ответ от оператора\n{text or ''}"

        try:
            if media_type in ('photo', 'voice', 'video', 'animation'):
                await getattr(bot, f'send_{media_type}')(
                    HISTORY_GROUP_ID, file_id, caption=caption
                )
            elif media_type == 'video_note':
                await bot.send_video_note(HISTORY_GROUP_ID, file_id)
            elif text:
                await bot.send_message(HISTORY_GROUP_ID, caption)
        except Exception as e:
            log.error("Ошибка при отправке истории: %s", e)
# legacy history handler for group
async def _unused_cmd_history_3(msg: Message):
    parts = msg.text.strip().split()
    if len(parts) != 3:
        return await msg.answer("⚠️ Формат: /history user_id limit")

    user_id, limit = parts[1], int(parts[2])
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT sender, text, file_id, media_type FROM history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        )
        rows = await cursor.fetchall()

    await msg.answer(f"📂 История с user_id {user_id} (последние {limit} сообщений)")
    for sender, text, file_id, media_type in reversed(rows):
        caption = text if sender == 'user' else f"📬 Ответ от оператора\n{text or ''}"
        try:
            if media_type in ('photo', 'voice', 'video', 'animation'):
                await getattr(bot, f'send_{media_type}')(HISTORY_GROUP_ID, file_id, caption=caption)
            elif media_type == 'video_note':
                await bot.send_video_note(HISTORY_GROUP_ID, file_id)
            elif text:
                await bot.send_message(HISTORY_GROUP_ID, caption)
        except Exception as e:
            log.error("Ошибка при отправке истории: %s", e)

# ==============================
# POSTING GROUP — новая версия
# ==============================

@dp.message(F.chat.id == POST_PLAN_GROUP_ID)
async def add_post_plan_button(msg: Message):
    """Добавляет кнопку 📆 Post Plan под каждым одиночным медиа в постинг-группе"""
    log.info(f"[POST_PLAN] Получено сообщение {msg.message_id} от {msg.from_user.id} в {msg.chat.id}")

    # Проверка: только админы
    if msg.from_user.id not in ADMINS:
        log.info(f"[POST_PLAN] Игнор: не админ ({msg.from_user.id})")
        return

    # Пропускаем альбомы
    if msg.media_group_id is not None:
        log.info(f"[POST_PLAN] Игнор: альбом (media_group_id={msg.media_group_id})")
        return

    # Только одиночные медиа (фото, видео, gif-анимация)
    if not (msg.photo or msg.video or msg.animation):
        log.info(f"[POST_PLAN] Игнор: не медиа ({msg.content_type})")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📆 Post Plan", callback_data=f"start_post_plan:{msg.message_id}")]]
    )

    global POST_COUNTER
    cnt = POST_COUNTER
    try:
        await bot.send_message(
            msg.chat.id,
            f"Пост №{cnt:03d}",
            reply_markup=kb,
            reply_to_message_id=msg.message_id,
        )
        log.info(f"[POST_PLAN] Кнопка добавлена (пост №{cnt:03d}) к сообщению {msg.message_id}")
        POST_COUNTER += 1
    except Exception as e:
        log.error(f"[POST_PLAN] Ошибка при добавлении кнопки: {e}")


@dp.callback_query(F.data.startswith("start_post_plan:"))
async def start_post_plan(cq: CallbackQuery, state: FSMContext):
    log.info(f"[POST_PLAN] Запуск планирования от {cq.from_user.id} в {cq.message.chat.id}")

    # Проверка чата
    if cq.message.chat.id != POST_PLAN_GROUP_ID:
        await cq.answer("⛔ Доступно только в постинг-группе", show_alert=True)
        return

    # Проверка на админа
    if cq.from_user.id not in ADMINS:
        await cq.answer("⛔ Только админы могут планировать посты", show_alert=True)
        return

    # Сохраняем ID исходного медиа
    try:
        msg_id = int(cq.data.split(":")[1])
        await state.update_data(source_message_id=msg_id)
    except Exception as e:
        log.error(f"[POST_PLAN] Ошибка парсинга message_id: {e}")
        return

    # Не очищаем state здесь, чтобы не потерять source_message_id
    await state.set_state(Post.wait_channel)
    await cq.message.answer("Куда постить?", reply_markup=post_plan_kb)


@dp.callback_query(F.data.startswith("post_to:"), Post.wait_channel)
async def post_choose_channel(cq: CallbackQuery, state: FSMContext):
    channel = cq.data.split(":")[1]
    # Сохраняем выбранный канал и ID исходного сообщения
    await state.update_data(channel=channel, source_message_id=cq.message.message_id)
    await state.set_state(Post.wait_content)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ Готово", callback_data="post_done")]]
    )
    await cq.message.edit_text("Пришли текст поста или медиа.", reply_markup=kb)
    log.info(f"[POST_PLAN] Выбран канал: {channel}")


@dp.message(Post.wait_content, F.chat.id == POST_PLAN_GROUP_ID)
async def post_content(msg: Message, state: FSMContext):
    data = await state.get_data()
    channel = data.get("channel")
    if not channel:
        log.error("[POST_PLAN] Ошибка: канал не выбран")
        await msg.reply("Ошибка: не выбран канал.")
        return

    if msg.photo or msg.video or msg.animation:
        ids = data.get("media_ids", [])
        if msg.photo:
            file_id = msg.photo[-1].file_id
            mtype = "photo"
        elif msg.video:
            file_id = msg.video.file_id
            mtype = "video"
        else:
            file_id = msg.animation.file_id
            mtype = "animation"
        ids.append(f"{mtype}:{file_id}")
        await state.update_data(media_ids=ids)
        if msg.caption:
            await state.update_data(text=msg.caption)
        await msg.reply("Медиа добавлено")
        log.info(f"[POST_PLAN] Добавлено медиа: {file_id}")
    elif msg.text:
        await state.update_data(text=msg.text)
        await msg.reply("Текст сохранён")
        log.info("[POST_PLAN] Сохранён текст поста")
    else:
        log.info("[POST_PLAN] Игнор: неподдерживаемый тип контента")


@dp.callback_query(Post.wait_content, F.data == "post_done")
async def post_done(cq: CallbackQuery, state: FSMContext):
    log.info(f"[POST_PLAN] post_done triggered: user_id={cq.from_user.id}")
    await cq.answer()
    state_name = await state.get_state()
    data = await state.get_data()
    log.info(
        f"[POST_PLAN] post_done: user_id={cq.from_user.id} chat_id={cq.message.chat.id} state={state_name} data={data}"
    )
    channel = data.get("channel")
    media_ids = ','.join(data.get("media_ids", []))
    text = data.get("text", "")
    source_msg_id = data.get("source_message_id", cq.message.message_id)
    ts = int(time.time())
    rowid = await _db_exec(
        "INSERT INTO scheduled_posts (created_ts, publish_ts, channel, price, text, from_chat_id, from_msg_id, media_ids, status, is_sent) VALUES(?,?,?,?,?,?,?,?,?,?)",
        int(time.time()),
        ts,
        channel,
        0,
        text,
        cq.message.chat.id,
        int(source_msg_id),
        media_ids,
        "scheduled",
        0,
        return_rowid=True,
    )
    log.info(f"[POST_PLAN] Запись добавлена в scheduled_posts rowid={rowid}")
    await cq.message.edit_text("✅ Пост запланирован!")
    await state.clear()
    log.info(f"[POST_PLAN] Пост запланирован в {channel}, медиа={media_ids}, текст={bool(text)}, source_msg_id={source_msg_id}")


async def scheduled_poster():
    log.debug("scheduled_poster called!")
    log.info("[POSTING PLAN] Стартовал планировщик scheduled_poster")
    while True:
        await asyncio.sleep(10)
        now = int(time.time())
        log.debug(f"[DEBUG] Checking scheduled_posts, now={now}")

        rows = await _db_fetchall(
            "SELECT rowid, publish_ts, channel, price, text, from_chat_id, from_msg_id, media_ids, status FROM scheduled_posts WHERE publish_ts <= ? AND status='scheduled' AND is_sent=0",
            now,
        )

        log.info(f"[DEBUG POSTER] найдено {len(rows)} пост(ов) к публикации")

        if not rows:
            log.debug("[SCHEDULED_POSTER] No posts scheduled for now.")

        for rowid, _, channel, price, text, from_chat, from_msg, media_ids, _status in rows:
            claimed = await _db_exec(
                "UPDATE scheduled_posts SET is_sent=1, status='sending' WHERE rowid=? AND is_sent=0 AND status='scheduled'",
                rowid,
                return_rowcount=True,
            )
            if not claimed:
                log.info(f"[SCHEDULED_POSTER] rowid={rowid} already claimed, skipping")
                continue
            chat_id = CHANNELS.get(channel)
            if not chat_id:
                log.warning(f"[SCHEDULED_POSTER] Channel {channel} not found in CHANNELS, skipping rowid={rowid}")
                continue
            log.debug(f"[DEBUG] Ready to post: rowid={rowid} channel={channel} text={text[:30]}")
            try:
                published = None
                sent_ids = []
                if media_ids:
                    ids = [tuple(item.split(':', 1)) for item in media_ids.split(',')]
                    if len(ids) == 1:
                        media_type, file_id = ids[0]
                        if media_type == "photo":
                            published = await bot.send_photo(chat_id, file_id, caption=text)
                        elif media_type == "video":
                            published = await bot.send_video(chat_id, file_id, caption=text)
                        else:
                            published = await bot.send_animation(chat_id, file_id, caption=text)
                        sent_ids.append(str(published.message_id))
                    else:
                        from aiogram.types import InputMediaPhoto, InputMediaVideo, InputMediaAnimation
                        media = []
                        for i, (media_type, file_id) in enumerate(ids):
                            if media_type == "photo":
                                m = InputMediaPhoto(media=file_id, caption=text if i == 0 else None)
                            elif media_type == "video":
                                m = InputMediaVideo(media=file_id, caption=text if i == 0 else None)
                            else:
                                m = InputMediaAnimation(media=file_id, caption=text if i == 0 else None)
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
                await _db_exec(
                    "UPDATE scheduled_posts SET status='failed', is_sent=0 WHERE rowid=?",
                    rowid,
                )
                continue
            except Exception as e:
                log.error(f"[FATAL POST FAIL] {e}\n{traceback.format_exc()}")
                await _db_exec(
                    "UPDATE scheduled_posts SET status='failed', is_sent=0 WHERE rowid=?",
                    rowid,
                )
                continue
            await asyncio.sleep(0.2)
            if published:
                await _db_exec("DELETE FROM scheduled_posts WHERE rowid = ?", rowid)
                # Query again to ensure the post won't be processed twice
                remaining = await _db_fetchone(
                    "SELECT COUNT(*) FROM scheduled_posts WHERE rowid=?",
                    rowid,
                )
                log.info(
                    f"[POST_PLAN] Пост rowid={rowid} успешно опубликован и удалён из очереди, remaining={remaining[0]}",
                )
                if remaining[0] == 0:
                    state_key = StorageKey(bot.id, from_chat, from_chat)
                    state = FSMContext(dp.storage, state_key)
                    await state.clear()
                    log.info(
                        f"[POST_PLAN] FSM state cleared after posting rowid={rowid}",
                    )
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

# ---------------- History command -------------------------
# Only respond to /history inside the configured history group
@dp.message(Command("history"), F.chat.id == HISTORY_GROUP_ID)
async def cmd_history(msg: Message):
    log.debug("Получена команда history из чата %s, ожидается %s", msg.chat.id, HISTORY_GROUP_ID)
    parts = msg.text.strip().split()
    if len(parts) not in (2, 3):
        await msg.reply("⚠️ Используй /history <user_id> [limit]")
        return
    try:
        uid = int(parts[1])
        limit = int(parts[2]) if len(parts) == 3 else 5
    except ValueError:
        await msg.reply("⚠️ Используй /history <user_id> [limit]")
        return

    messages = await get_last_messages(uid, limit)
    if not messages:
        await msg.reply("📭 Нет сообщений")
        return

    for item in messages:
        await send_to_history(bot, HISTORY_GROUP_ID, item)

# ---------------- Run bot + aiohttp -----------------------
async def main():
    log.debug("Inside main()")
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

@dp.message(Command("test_vip"))
async def test_vip_post(msg: Message):
    if msg.from_user.id not in ADMINS:
        await msg.reply("⛔️ Нет доступа.")
        return
    try:
        await bot.send_message(CHANNELS["vip"], "✅ Проверка: бот может писать в VIP")
        await msg.reply("✅ Успешно отправлено в VIP-канал")
    except Exception as e:
        log.error("Ошибка при отправке в VIP: %s", e)

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
    if chat_id not in [CHANNELS["vip"], LIFE_CHANNEL_ID, CHANNELS["luxury"]]:
        await msg.reply(tr(lang, 'not_allowed_channel'))
        return
    try:
        await bot.delete_message(chat_id, msg_id)
        await msg.reply(tr(lang, 'post_deleted'))
    except Exception as e:
        log.error("Ошибка удаления: %s", e)


async def setup_webhook():
    session = AiohttpSession()
    bot = Bot(token=getenv("TELEGRAM_TOKEN"), session=session)
    webhook_url = getenv("WEBHOOK_URL")
    await bot.set_webhook(webhook_url)



# --- Codex-hack: TEMPORARY DISABLE AUTO-START FOR CODEX ---
# if __name__ == "__main__":
#     # Avoid starting an extra aiohttp server when running under gunicorn
#     if "gunicorn" not in os.getenv("SERVER_SOFTWARE", "").lower():
#         asyncio.run(setup_webhook())
#         print("DEBUG: JuicyFox main() will run")
#         asyncio.run(main())
# --- END Codex-hack ---
