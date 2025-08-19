# JuicyFox Bot — single‑file (aiogram 3.20) + 30‑day access
# ---------------------------------------------------------
# • Club / VIP / Chat  → 8 валют → счёт → доступ ровно 30 суток
# • Donate             → валюта → сумма (USD) → счёт
# • Relay              → приват ↔ группа (CHAT_GROUP_ID)
# • RU/EN/ES UI           → auto by language_code

import os
import logging
log = logging.getLogger(__name__)
import httpx
import time
import aiosqlite
import traceback
import sqlite3
import asyncio
from os import getenv
from aiogram import Bot
from datetime import datetime, timedelta
import calendar
from types import SimpleNamespace

os.makedirs("/app/data", exist_ok=True)
DB_PATH = "/app/data/juicyfox.db"

if not os.path.exists(DB_PATH):
    with sqlite3.connect(DB_PATH) as db:
        db.execute('CREATE TABLE IF NOT EXISTS messages (uid INTEGER, sender TEXT, text TEXT, file_id TEXT, media_type TEXT, timestamp INTEGER)')

def migrate_add_ts_column():
    pass

from typing import Dict, Any, Optional, Tuple, List
from aiogram import Dispatcher, Router, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, Update
from aiogram.utils.keyboard import InlineKeyboardBuilder

from router_pay import router as router_pay
from router_access import router as router_access
from router_posting import router as router_posting
from router_history import router as router_history

from modules.ui_membership.handlers import router as router_ui
from modules.common.shared import CURRENCIES, LIFE_URL, ChatGift, create_invoice, tr


from router_relay import router as router_relay


@router_relay.message(Command("relay_test"))
async def relay_stub(message: Message):
    lang = message.from_user.language_code
    await message.answer(tr(lang, "relay_unavailable"))


@router_history.message(Command("history_test"))
async def history_stub(message: Message):
    lang = message.from_user.language_code
    await message.answer(tr(lang, "history_unavailable"))


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



from aiogram.fsm.state import StatesGroup, State


class Post(StatesGroup):
    wait_channel = State()
    select_datetime = State()
    wait_time = State()
    wait_minute = State()
    select_stars = State()
    wait_description = State()
    wait_price = State()
    wait_content = State()
    wait_confirm = State()



WAIT_TIME = Post.wait_time
WAIT_MINUTE = Post.wait_minute


WAIT_DATE = Post.select_datetime
WAIT_TIME = Post.wait_time
WAIT_MINUTE = Post.wait_minute



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


os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/runtime.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
log.info("\ud83d\udd25 Bot launched successfully")


class UpdateLogger(BaseMiddleware):
    async def __call__(self, handler, event, data):
        logging.info(f"Incoming update: {event}")
        return await handler(event, data)


def relay_error_handler(func):
    async def wrapper(msg: Message, *a, **kw):
        try:
            return await func(msg, *a, **kw)
        except Exception as e:
            log.error("%s error: %s", func.__name__, e)
            tb = traceback.format_exc()
            print(f"{func.__name__} error: {e}\n{tb}")
    return wrapper


def extract_media(msg: Message):
    text = msg.text or msg.caption or ''
    fid = mtype = None
    if msg.photo:
        fid, mtype = msg.photo[-1].file_id, 'photo'
    elif msg.video:
        fid, mtype = msg.video.file_id, 'video'
    elif msg.document:
        fid, mtype = msg.document.file_id, 'document'
    elif msg.voice:
        fid, mtype = msg.voice.file_id, 'voice'
    elif msg.audio:
        fid, mtype = msg.audio.file_id, 'audio'
    elif msg.animation:
        fid, mtype = msg.animation.file_id, 'animation'
    elif msg.video_note:
        fid, mtype = msg.video_note.file_id, 'video_note'
    elif msg.sticker:
        fid, mtype = msg.sticker.file_id, 'sticker'
    elif msg.contact:
        fid, mtype = msg.contact.phone_number, 'contact'
    elif msg.location:
        fid, mtype = f"{msg.location.longitude},{msg.location.latitude}", 'location'
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
            await bot.send_message(chat_id, tr("ru", "operator_reply_no_text"))
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

BASE_URL = os.getenv("BASE_URL")
BOT_ID_ENV = os.getenv("BOT_ID")
if not BOT_ID_ENV:
    raise RuntimeError("BOT_ID environment variable is required")
BOT_ID = int(BOT_ID_ENV)
WEBHOOK_URL = f"{BASE_URL}/webhook/bot/{BOT_ID}/webhook"

# --- Codex-hack: TEMPORARY DISABLE env checks for Codex PR ---
# if not TELEGRAM_TOKEN or not CRYPTOBOT_TOKEN:
#     raise RuntimeError('Set TELEGRAM_TOKEN and CRYPTOBOT_TOKEN env vars')
# --- END Codex-hack ---

# Retrieve and validate chat group ID from environment
CHAT_GROUP_ID_ENV = getenv("CHAT_GROUP_ID")
if not CHAT_GROUP_ID_ENV:
    raise RuntimeError("CHAT_GROUP_ID environment variable is required")
CHAT_GROUP_ID = int(CHAT_GROUP_ID_ENV)
# Cast HISTORY_GROUP_ID to int so numeric chat IDs match correctly
HISTORY_GROUP_ID = int(getenv("HISTORY_GROUP_ID"))
ADMINS = [7893194894]
LIFE_CHANNEL_ID = int(os.getenv("LIFE_CHANNEL_ID"))

API_BASE        = 'https://pay.crypt.bot/api'
VIP_URL = os.getenv("VIP_URL")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))

CHANNELS = {
    "life": LIFE_CHANNEL_ID,
    "luxury": int(os.getenv("LUXURY_CHANNEL_ID")),
    "vip": int(os.getenv("VIP_CHANNEL_ID")),
    # Use the configured chat group for 30-day chat access
    "chat_30": CHAT_GROUP_ID,
}

# Default tariff description for each posting channel
CHANNEL_TARIFFS = {
    "life": "channel_tariff_life",
    "vip": "channel_tariff_vip",
    "luxury": "channel_tariff_luxury",
}

PAID_CHANNELS = {"vip", "luxury"}

def is_paid_channel(channel: str) -> bool:
    return channel in PAID_CHANNELS

log.info(
    "Env CHAT_GROUP_ID=%s HISTORY_GROUP_ID=%s LIFE_CHANNEL_ID=%s POST_PLAN_GROUP_ID=%s",
    CHAT_GROUP_ID,
    HISTORY_GROUP_ID,
    LIFE_CHANNEL_ID,
    POST_PLAN_GROUP_ID,
)

# --- Startup ------------------------------------------------
async def bot_startup(bot: Bot):
    log.info("on_startup called")
    await _db_exec(
        "CREATE TABLE IF NOT EXISTS reply_links (reply_msg_id INTEGER PRIMARY KEY, user_id INTEGER)"
    )
    asyncio.create_task(scheduled_poster())


bot: Optional[Bot] = None
bot_pool: Dict[str, Bot] = {}
dp  = Dispatcher(storage=MemoryStorage())
dp.update.outer_middleware(UpdateLogger())
dp.startup.register(bot_startup)

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
            try:
                chat = await bot.get_chat(user_id)
                lang = chat.language_code or 'ru'
            except Exception:
                lang = 'ru'
            await bot.send_message(user_id, tr(lang, 'vip_access_link', link=link.invite_link))
        except TelegramBadRequest as e:
            log.warning('Cannot give VIP link: %s', e)

async def give_club_channel(user_id: int):
    try:
        await bot.add_chat_member(CHANNELS["luxury"], user_id)
    except TelegramForbiddenError:
        try:
            link = await bot.create_chat_invite_link(CHANNELS["luxury"], member_limit=1, expire_date=int(time.time())+3600)
            try:
                chat = await bot.get_chat(user_id)
                lang = chat.language_code or 'ru'
            except Exception:
                lang = 'ru'
            await bot.send_message(user_id, tr(lang, 'luxury_access_link', link=link.invite_link))
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
CREATE TABLE IF NOT EXISTS events(
  key TEXT PRIMARY KEY,
  post_id INTEGER,
  run_at INTEGER,
  channel TEXT,
  text TEXT,
  media_ids TEXT
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
            if not row: return tr('ru', 'no_access')
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

# ----- Data -----
relay: dict[int, int] = {}  # group_msg_id -> user_id
TARIFFS={'club':15.00,'vip':35.00}
CHAT_TIERS={7:5.0,15:9.0,30:15.0}
@router_pay.callback_query(F.data.startswith('pay:'))
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
    kb.button(text=tr(lang, 'back'), callback_data="back")
    kb.adjust(2)
    if plan == 'club':
        text = tr(lang, 'luxury_room_desc')
    else:
        text = tr(lang, 'choose_cur', amount=amt)
    await cq.message.edit_text(text, reply_markup=kb.as_markup())


@router_pay.callback_query(F.data.startswith('payc:'))
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
        lang = cq.from_user.language_code
        await cq.message.edit_text(tr(lang, 'invoice_message', plan=plan.upper(), url=url))
        
    else:
        await cq.answer(tr(cq.from_user.language_code,'inv_err'),show_alert=True)

@router_pay.callback_query(F.data.startswith('vipay:'))
async def handle_vip_currency(cq: CallbackQuery):
    cur = cq.data.split(':')[1]
    amt = TARIFFS['vip']
    url = await create_invoice(cq.from_user.id, amt, cur, 'JuicyFox Subscription', pl='vip')
    if url:
        lang = cq.from_user.language_code
        await cq.message.edit_text(tr(lang, 'invoice_message', plan='VIP', url=url))
    else:
        await cq.answer(tr(cq.from_user.language_code,'inv_err'), show_alert=True)

@router_pay.callback_query(F.data.startswith('chatgift:'), ChatGift.choose_tier)
async def chatgift_currency(cq: CallbackQuery, state: FSMContext):
    days = int(cq.data.split(':')[1])
    amt = CHAT_TIERS.get(days, 0)
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f'payc:chat:{days}:{c}')
    kb.button(text=tr(cq.from_user.language_code, 'back'), callback_data="back")
    kb.adjust(2)
    await cq.message.edit_text(
        tr(cq.from_user.language_code, 'choose_cur', amount=amt),
        reply_markup=kb.as_markup(),
    )
    await state.clear()


# ---------------- Relay private ↔ group -------------------


@dp.message(F.chat.type == 'private')
@relay_error_handler
async def relay_private(msg: Message, state: FSMContext, **kwargs):
    # Игнорируем любые команды в приватных сообщениях
    cmd_text = msg.text or msg.caption or ""
    if cmd_text.startswith('/'):
        return
    if not getattr(msg, "from_user", None):
        log.warning("[RELAY] message without from_user: %s", msg)
        return
    log.info("[RELAY] checking access for user=%s", msg.from_user.id)
    try:
        paid = await is_paid(msg.from_user.id)
    except Exception as e:
        log.error("[RELAY] is_paid error for %s: %s", msg.from_user.id, e)
        paid = False

    if not paid:
        await msg.reply(tr(msg.from_user.language_code, 'access_denied'))
        return

    cnt = await inc_msg(msg.from_user.id)
    log.info("[RELAY] inc_msg(%s) -> %s", msg.from_user.id, cnt)
    if cnt > CONSECUTIVE_LIMIT:
        log.info(
            "[RELAY] blocked by limit: user=%s count=%s",
            msg.from_user.id,
            cnt,
        )
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

    log.warning(
        "[DEBUG RELAY] sending header to group=%s from=%s msg_id=%s header=%r",
        CHAT_GROUP_ID,
        msg.chat.id,
        msg.message_id,
        header,
    )
    try:
        header_msg = await bot.send_message(CHAT_GROUP_ID, header, parse_mode="HTML")
        log.warning("[DEBUG RELAY] Header sent OK msg_id=%s", header_msg.message_id)
    except Exception as e:
        log.warning("[DEBUG RELAY] send_message failed: %s", e)
        return
    relay[header_msg.message_id] = msg.from_user.id

    log.warning(
        "[DEBUG RELAY] copying message to group=%s from=%s msg_id=%s",
        CHAT_GROUP_ID,
        msg.chat.id,
        msg.message_id,
    )
    try:
        cp = await bot.copy_message(CHAT_GROUP_ID, msg.chat.id, msg.message_id)
        log.warning("[DEBUG RELAY] Message copied OK msg_id=%s", cp.message_id)
    except Exception as e:
        log.warning("[DEBUG RELAY] copy_message failed: %s", e)
        return
    relay[cp.message_id] = msg.from_user.id

    # Запись связей и сообщения в базу
    async with aiosqlite.connect(DB_PATH) as db:
        for mid in (header_msg.message_id, cp.message_id):
            await db.execute(
                "INSERT OR REPLACE INTO reply_links (reply_msg_id, user_id) VALUES (?, ?)",
                (mid, msg.from_user.id),
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

    # Только администраторы могут отвечать пользователю
    admins = {a.user.id for a in await msg.chat.get_administrators()}
    if not uid or msg.from_user.id not in admins:
        return

    text, fid, mtype = extract_media(msg)
    log.info(
        "[RELAY_GROUP] send to user=%s via group=%s text=%r",
        uid,
        CHAT_GROUP_ID,
        text,
    )
    try:
        await bot.copy_message(uid, CHANNELS["chat_30"], msg.message_id)
    except Exception as e:
        log.error("[RELAY_GROUP] copy_message error (%s): %s", type(e).__name__, e)
        return
    # await send_to_history(bot, HISTORY_GROUP_ID, msg)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (uid, sender, text, file_id, media_type, timestamp) VALUES (?,?,?,?,?,?)",
            (uid, 'admin', text, fid, mtype, int(time.time())),
        )
        await db.commit()

# legacy history handler
async def _unused_cmd_history_2(msg: Message):
    print(f"Received /history in chat: {msg.chat.id}, text: {msg.text}")
    print(f"[DEBUG] /history called, chat_id={msg.chat.id}, text={msg.text}")
    lang = msg.from_user.language_code
    if msg.chat.id != HISTORY_GROUP_ID:
        print(f"[ERROR] /history used outside history group: chat_id={msg.chat.id}")
        await msg.reply(tr(lang, 'history_only_chat'))
        return

    args = msg.text.split()
    if len(args) != 3:
        print(f"[ERROR] /history invalid args count: {msg.text}")
        await msg.reply(tr(lang, 'invalid_syntax'))
        return

    try:
        uid = int(args[1])
        limit = int(args[2])
    except ValueError:
        print(f"[ERROR] /history invalid uid/limit: {msg.text}")
        await msg.reply(tr(lang, 'invalid_syntax'))
        return

    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall(
            'SELECT sender, text, file_id, media_type FROM messages WHERE uid = ? ORDER BY timestamp DESC LIMIT ?',
            (uid, limit)
        )

    if not rows:
        await msg.reply(tr(lang, 'history_no_messages'))
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
            print(f"Ошибка при отправке истории: {e}")
# legacy history handler for group
async def _unused_cmd_history_3(msg: Message):
    lang = msg.from_user.language_code
    parts = msg.text.strip().split()
    if len(parts) != 3:
        return await msg.answer(tr(lang, 'history_format'))

    user_id, limit = parts[1], int(parts[2])
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT sender, text, file_id, media_type FROM history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        )
        rows = await cursor.fetchall()

    await msg.answer(tr(lang, 'history_header', user_id=user_id, limit=limit))
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
            print(f"Ошибка при отправке истории: {e}")

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
            tr(msg.from_user.language_code, 'post_number', num=cnt),
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
    lang = cq.from_user.language_code

    # Проверка чата
    if cq.message.chat.id != POST_PLAN_GROUP_ID:
        await cq.answer(tr(lang, 'posting_only_group'), show_alert=True)
        return

    # Проверка на админа
    if cq.from_user.id not in ADMINS:
        await cq.answer(tr(lang, 'posting_admin_only'), show_alert=True)
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
    await cq.message.answer(tr(lang, 'where_post'), reply_markup=post_plan_kb)


def kb_days(d: Dict[str, int], lang: str):
    """Build keyboard for selecting a day."""
    y, m, selected_day = d["y"], d["m"], d.get("d")
    cal = calendar.monthcalendar(y, m)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=f"{y}-{m:02d}", callback_data="noop"))
    for w in cal:
        row_buttons = []
        for x in w:
            text = " " if x == 0 else (f"[{x}]" if x == selected_day else str(x))
            callback_data = "noop" if x == 0 else f"d:{x}"
            logging.info(f"Generated date button callback: {callback_data}")
            row_buttons.append(InlineKeyboardButton(text=text, callback_data=callback_data))
        kb.row(*row_buttons)
    kb.row(InlineKeyboardButton(text=tr(lang, "dt_cancel"), callback_data="cancel"))
    return kb.as_markup()


def get_time_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Build inline keyboard for selecting time."""
    kb = InlineKeyboardBuilder()
    for r in range(4):
        kb.row(
            *[
                InlineKeyboardButton(
                    text=tr(lang, "choose_time", time=f"{h:02d}:00"),
                    callback_data=f"h:{h}",
                )
                for h in range(r * 6, (r + 1) * 6)
            ]
        )
    kb.row(InlineKeyboardButton(text=tr(lang, "dt_cancel"), callback_data="cancel"))
    return kb.as_markup()


def kb_hours(d: Dict[str, int], lang: str):
    """Build keyboard for selecting an hour."""
    selected_hour = d.get("h")
    kb = InlineKeyboardBuilder()
    for r in range(4):
        kb.row(
            *[
                InlineKeyboardButton(
                    text=f"[{h:02d}]" if h == selected_hour else f"{h:02d}",
                    callback_data=f"h:{h}",
                )
                for h in range(r * 6, (r + 1) * 6)
            ]
        )
    kb.row(InlineKeyboardButton(text=tr(lang, "dt_cancel"), callback_data="cancel"))
    return kb.as_markup()


def kb_minutes(data: Dict[str, int], lang: str):
    kb = InlineKeyboardBuilder()
    for m in [0, 15, 30, 45]:
        kb.button(text=f"{m:02d}", callback_data=f"mi:{m:02d}")
    kb.adjust(4)
    return kb.as_markup()


def stars_kb(lang: str) -> InlineKeyboardMarkup:
    """Stars selection keyboard for LIFE channel."""
    builder = InlineKeyboardBuilder()
    stars_values = [50, 100, 200, 300, 400, 600, 800, 1000]
    for val in stars_values:
        builder.button(text=f"{val}⭐️", callback_data=f"stars:{val}")
    builder.button(text=tr(lang, 'free_label'), callback_data="stars:FREE")
    builder.adjust(4)
    return builder.as_markup()


def done_kb(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang, 'done_label'), callback_data='post_done')
    return b.as_markup()

@dp.callback_query(F.data.startswith("post_to:"), Post.wait_channel)
async def post_choose_channel(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    channel = cq.data.split(":")[1]
    lang = cq.from_user.language_code
    data_update = {"channel": channel}
    if channel != "life":
        tariff_key = CHANNEL_TARIFFS.get(channel, "")
        data_update["tariff"] = tr(lang, tariff_key) if tariff_key else ""
    await state.update_data(**data_update)
    now = datetime.now()
    data = {
        "y": now.year,
        "m": now.month,
        "d": now.day,
        "h": now.hour,
        "mi": 0,
    }
    await state.update_data(**data)

    await cq.message.edit_text(
        tr(cq.from_user.language_code, "dt_prompt"),
        reply_markup=kb_days(data, cq.from_user.language_code),
    )
    log.info(f"[POST_PLAN] Выбран канал: {channel}")



async def dt_callback(callback_query: CallbackQuery, state: FSMContext):
    logging.info(f"WAIT_DATE callback received: {callback_query.data}")
    data = await state.get_data()
    act, val = (callback_query.data.split(':') + ['0'])[:2]
    if act == 'noop':
        await callback_query.answer()
        return
    lang = callback_query.from_user.language_code
    if act == 'd':

        d = int(val)
        if d == 0:
            await callback_query.answer()
            return
        await state.update_data(d=d)
        await state.set_state(WAIT_TIME)
        await callback_query.message.edit_reply_markup(reply_markup=get_time_keyboard(lang))
        log.info(f"[POST_PLAN] Selected day: {d}")
    elif act == 'h':

        h = int(val)
        await state.update_data(h=h)
        await state.set_state(Post.wait_minute)

        log.info(f"[POST_PLAN][WAIT_TIME] data: {callback_query.data}")
        h = int(val)
        await state.update_data(h=h)
        await state.set_state(WAIT_MINUTE)

        data = await state.get_data()
        kb = InlineKeyboardBuilder()
        for m in [0, 15, 30, 45]:
            kb.button(text=f"{m:02d}", callback_data=f"mi:{m:02d}")
        kb.adjust(4)
        await callback_query.message.edit_caption(
            caption=tr(lang, 'choose_minute'),

            reply_markup=kb.as_markup()
        )
        log.info(f"[POST_PLAN] Selected hour: {h} → waiting minute selection")
    
    elif act == 'mi':
        log.info(f"[POST_PLAN][WAIT_MINUTE] data: {callback_query.data}")

        mi = int(val)
        await state.update_data(mi=mi)
        data = await state.get_data()
        log.info(f"[POST_PLAN] Selected minute: {mi}")
        ts = int(datetime(data['y'], data['m'], data['d'], data['h'], data['mi']).timestamp())
        channel = data.get("channel")
        await state.update_data(publish_ts=ts)
        if channel == "life":
            await state.set_state(Post.select_stars)
            log.info(f"[POST_PLAN] Transition to Post.select_stars (channel={channel})")
            await callback_query.message.edit_text(tr(lang, 'ask_stars'), reply_markup=stars_kb(lang))
        else:
            tariff_key = CHANNEL_TARIFFS.get(channel, "")
            tariff = tr(lang, tariff_key) if tariff_key else ""
            await state.update_data(tariff=tariff)
            await state.set_state(Post.wait_content)
            log.info(f"[POST_PLAN] Transition to Post.wait_content (channel={channel})")
            await callback_query.message.edit_text(tr(lang, 'ask_content'), reply_markup=done_kb(lang))
    elif act == 'cancel':


        log.info(f"[POST_PLAN] Cancel data: {callback_query.data}")

        await callback_query.message.edit_text(tr(lang, 'cancel'))
        await state.clear()
    await callback_query.answer()

@dp.callback_query(F.data.startswith("stars:"), Post.select_stars)
async def stars_selected(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    lang = cq.from_user.language_code
    val = cq.data.split(":")[1]
    if val == "FREE":
        tariff = "FREE"
    else:
        tariff = f"{val} Stars⭐️"
    await state.update_data(tariff=tariff)
    log.info(f"[POST_PLAN] Selected Stars: {tariff}")
    await state.set_state(Post.wait_content)
    log.info("[POST_PLAN] Transition to Post.wait_content")
    await cq.message.edit_text(tr(lang, 'ask_content'), reply_markup=done_kb(lang))

@dp.message(Post.wait_description, F.chat.id == POST_PLAN_GROUP_ID)
async def post_description(msg: Message, state: FSMContext):
    lang = msg.from_user.language_code
    desc = msg.text or ''
    await state.update_data(description=desc)
    data = await state.get_data()
    if is_paid_channel(data.get('channel')):
        await state.update_data(price=None)
        await state.set_state(Post.wait_price)
        await msg.answer(tr(lang, 'set_price_prompt'))
    else:
        await state.set_state(Post.wait_content)
        await msg.answer(tr(lang, 'ask_content'), reply_markup=done_kb(lang))

@dp.message(Post.wait_price, F.chat.id == POST_PLAN_GROUP_ID)
async def post_price(msg: Message, state: FSMContext):
    lang = msg.from_user.language_code
    await state.update_data(price=msg.text)
    await state.set_state(Post.wait_content)
    await msg.answer(tr(lang, 'ask_content'), reply_markup=done_kb(lang))

@dp.message(Post.wait_content, F.chat.id == POST_PLAN_GROUP_ID)
async def post_content(msg: Message, state: FSMContext):
    data = await state.get_data()
    channel = data.get("channel")
    if not channel:
        log.error("[POST_PLAN] Ошибка: канал не выбран")
        await msg.reply(tr(msg.from_user.language_code, 'post_channel_not_selected'))
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
        await msg.reply(tr(msg.from_user.language_code, 'media_added'))
        log.info(f"[POST_PLAN] Добавлено медиа: {file_id}")
    elif msg.text:
        await state.update_data(text=msg.text)
        await msg.reply(tr(msg.from_user.language_code, 'text_saved'))
        log.info("[POST_PLAN] Сохранён текст поста")
    else:
        log.info("[POST_PLAN] Игнор: неподдерживаемый тип контента")


@dp.callback_query(F.data == "post_done")
async def post_done(cq: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    log.info("[POST_PLAN] post_done triggered, state=%s, data=%s", await state.get_state(), data)
    await cq.answer()
    channel = data["channel"]
    media_ids = ','.join(data.get("media_ids", []))
    text = data.get("text", "")
    source_msg_id = data.get("source_message_id", cq.message.message_id)
    ts = data["publish_ts"]
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

    event_key = f"{rowid}:{ts}"
    await _db_exec(
        "INSERT OR IGNORE INTO events (key, post_id, run_at, channel, text, media_ids) VALUES (?,?,?,?,?,?)",
        event_key,
        rowid,
        ts,
        channel,
        text,
        media_ids,
    )
    log.info(f"[POST_PLAN] Event published key={event_key}")

    lang = cq.from_user.language_code
    date_str = f"{data['d']:02d}.{data['m']:02d}.{data['y']}"
    time_str = f"{data['h']:02d}:{data['mi']:02d}"
    tariff_str = data["tariff"]
    await cq.message.edit_reply_markup()
    await cq.message.answer(
        tr(lang, 'post_scheduled').format(
            channel=channel.upper(),
            date=date_str,
            time=time_str,
            tariff=tariff_str,
        )
    )
    log.info(f"[POST_PLAN] Пост запланирован в {channel}, медиа={media_ids}, текст={bool(text)}, source_msg_id={source_msg_id}")
    await state.clear()





async def notify_log_channel(text: str):
    if LOG_CHANNEL_ID:
        await bot.send_message(LOG_CHANNEL_ID, text)

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
                log.warning(f"[SCHEDULED_POSTER] channel={channel} rowid={rowid} not found in CHANNELS")
                continue
            log.debug(f"[DEBUG] Ready to post: rowid={rowid} channel={channel} text={text[:30]}")
            post_data = {
                "text": text,
                "media_ids": media_ids,
                "from_chat": from_chat,
                "from_msg": from_msg,
            }
            log.info(
                f"[SCHEDULED_POSTER] rowid={rowid} channel={channel} data={post_data}"
            )
            try:
                published = None
                sent_ids = []
                if media_ids:
                    ids = [tuple(item.split(':', 1)) for item in media_ids.split(',')]
                    if len(ids) == 1:
                        media_type, file_id = ids[0]
                        if not chat_id or not (file_id or text):
                            log.warning(f"[POST SKIPPED] rowid={rowid} channel={channel} chat_id={chat_id} file_id={file_id} text={text}"); await notify_log_channel(f"Post skipped: channel={channel}, reason=empty data"); continue
                        try:
                            if media_type == "photo":
                                published = await bot.send_photo(chat_id, file_id, caption=text)
                            elif media_type == "video":
                                published = await bot.send_video(chat_id, file_id, caption=text)
                            else:
                                published = await bot.send_animation(chat_id, file_id, caption=text)
                        except Exception as e: log.error(f"[POST ERROR] rowid={rowid} channel={channel} {e}"); await notify_log_channel(f"Post error in channel={channel}: {e}"); continue
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
                        try:
                            grp = await bot.send_media_group(chat_id, media)
                        except Exception as e: log.error(f"[POST ERROR] rowid={rowid} channel={channel} {e}"); await notify_log_channel(f"Post error in channel={channel}: {e}"); continue
                        if grp:
                            published = grp[0]
                            sent_ids = [str(m.message_id) for m in grp]
                elif not media_ids and text:
                    if not chat_id or not text:
                        log.warning(f"[POST SKIPPED] rowid={rowid} channel={channel} chat_id={chat_id} file_id=None text={text}"); await notify_log_channel(f"Post skipped: channel={channel}, reason=empty data"); continue
                    try:
                        published = await bot.send_message(chat_id, text, disable_notification=True)
                    except Exception as e: log.error(f"[POST ERROR] rowid={rowid} channel={channel} {e}"); await notify_log_channel(f"Post error in channel={channel}: {e}"); continue
                    sent_ids.append(str(published.message_id))
                elif text == '<media>' or not text:
                    if not chat_id or (not from_msg and not text):
                        log.warning(f"[POST SKIPPED] rowid={rowid} channel={channel} chat_id={chat_id} file_id={from_msg} text={text}"); await notify_log_channel(f"Post skipped: channel={channel}, reason=empty data"); continue
                    try:
                        published = await bot.copy_message(chat_id, from_chat, from_msg)
                    except Exception as e: log.error(f"[POST ERROR] rowid={rowid} channel={channel} {e}"); await notify_log_channel(f"Post error in channel={channel}: {e}"); continue
                    sent_ids.append(str(published.message_id))
                else:
                    if not chat_id or (not from_msg and not text):
                        log.warning(f"[POST SKIPPED] rowid={rowid} channel={channel} chat_id={chat_id} file_id={from_msg} text={text}"); await notify_log_channel(f"Post skipped: channel={channel}, reason=empty data"); continue
                    try:
                        published = await bot.copy_message(chat_id, from_chat, from_msg, caption=text)
                    except Exception as e: log.error(f"[POST ERROR] rowid={rowid} channel={channel} {e}"); await notify_log_channel(f"Post error in channel={channel}: {e}"); continue
                    sent_ids.append(str(published.message_id))
                log.info(f"[POST OK] rowid={rowid} channel={channel}")
                if published:
                    await _db_exec(
                        "INSERT INTO published_posts (chat_id, message_id) VALUES (?, ?)",
                        published.chat.id,
                        published.message_id,
                    )
            except TelegramBadRequest as e:
                log.warning(f"[POST FAIL] rowid={rowid} channel={channel} {e}")
                await _db_exec(
                    "UPDATE scheduled_posts SET status='failed', is_sent=0 WHERE rowid=?",
                    rowid,
                )
                continue
            except Exception as e:
                log.error(f"[FATAL POST FAIL] rowid={rowid} channel={channel} {e}\n{traceback.format_exc()}")
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
                log.info(
                    f"[SCHEDULED_POSTER] sent message_ids for rowid={rowid}: {sent_ids}"
                )
                await bot.send_message(
                    POST_PLAN_GROUP_ID,
                    f"✅ Пост опубликован! Для удаления: /delete_post {published.message_id}",
                )


# ---------------- Mount & run -----------------------------
dp.include_router(router_pay)
log.info("router_pay registered")
dp.include_router(router_access)
log.info("router_access registered")
dp.include_router(router_posting)
log.info("router_posting registered")
dp.include_router(router_relay)
log.info("router_relay registered")
dp.include_router(router_history)
log.info("router_history registered")
dp.include_router(router_ui)
log.info("router_ui registered")


# ---------------- Webhook server --------------------------
from aiohttp import web, ClientSession, ClientConnectorError, ClientTimeout

async def telegram_webhook_handler(request: web.Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_webhook_update(bot, update)
    return web.Response()


async def on_startup(app):
    await dp.emit_startup(bot)


async def on_shutdown(app):
    await dp.emit_shutdown(bot)


async def cryptobot_hook(request: web.Request):
    """Принимаем invoice_paid от CryptoBot и выдаём доступ"""
    data = await request.json()
    if data.get('update_type') != 'invoice_paid' or data.get('status') != 'paid':
        return web.json_response({'ok': True})

    payload = data.get('payload')
    if not payload:
        log.warning("No payload in webhook data: %s", data)
        return web.Response(status=400)

    amount = data.get('amount')
    if not amount:
        log.warning('[WEBHOOK] Missing amount in update: %s', data)
        return web.Response(status=400)

    payload_str = payload
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
            usd_amt = float(amount) * rates.get(asset.upper(), 0)
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
@router_history.message(Command("history"), F.chat.id == HISTORY_GROUP_ID)
async def cmd_history(msg: Message):
    print(f"[DEBUG] Получена команда history из чата {msg.chat.id}, ожидается {HISTORY_GROUP_ID}")
    parts = msg.text.strip().split()
    if len(parts) not in (2, 3):
        await msg.reply(tr(msg.from_user.language_code, 'history_usage'))
        return
    try:
        uid = int(parts[1])
        limit = int(parts[2]) if len(parts) == 3 else 5
    except ValueError:
        await msg.reply(tr(msg.from_user.language_code, 'history_usage'))
        return

    messages = await get_last_messages(uid, limit)
    if not messages:
        await msg.reply(tr(msg.from_user.language_code, 'history_no_messages'))
        return

    for item in messages:
        await send_to_history(bot, HISTORY_GROUP_ID, item)

# ---------------- Run bot + aiohttp -----------------------
async def main():
    log.info("main() started")
    if not TELEGRAM_TOKEN:
        log.error("TELEGRAM_TOKEN is empty or not set")
        return

    global bot
    bot = Bot(token=TELEGRAM_TOKEN, parse_mode='HTML')

    test_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"
    try:
        timeout = ClientTimeout(total=5)
        async with ClientSession(timeout=timeout) as session:
            async with session.get(test_url) as resp:
                if resp.status != 200:
                    log.error("Проверьте BOT_TOKEN: %s", await resp.text())
                    return
                data = await resp.json()
                if not data.get("ok"):
                    log.error("Проверьте BOT_TOKEN: %s", data)
                    return
        log.info("Test connection to Telegram API succeeded")
    except ClientConnectorError as e:
        log.error("Нет доступа к Telegram API: %s", e)
        return
    except asyncio.TimeoutError:
        log.error("Нет доступа к Telegram API: timeout")
        return

    try:
        me = await bot.get_me()
    except ClientConnectorError as e:
        log.error("Нет доступа к Telegram API: %s", e)
        return
    except asyncio.TimeoutError:
        log.error("Нет доступа к Telegram API: timeout")
        return
    except TelegramBadRequest as e:
        log.error("Проверьте BOT_TOKEN: %s", e)
        return
    bot_pool[str(me.id)] = bot
    allowed_updates = dp.resolve_used_update_types()
    if "callback_query" not in allowed_updates:
        allowed_updates.append("callback_query")
    await bot.set_webhook(
        WEBHOOK_URL,
        drop_pending_updates=True,
        allowed_updates=allowed_updates,
    )

    log.info("Webhook set successfully")

    log.info("Webhook installed at %s", WEBHOOK_URL)

    # aiohttp web‑server
    app = web.Application()
    app.router.add_post(f"/webhook/bot/{BOT_ID}/webhook", telegram_webhook_handler)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    log.info('Webhook server started on 0.0.0.0:8080 /webhook/bot/%s/webhook', BOT_ID)
    log.info('JuicyFox Bot ready for webhooks')
    await asyncio.Event().wait()

@dp.message(Command("test_vip"))
async def test_vip_post(msg: Message):
    if msg.from_user.id not in ADMINS:
        await msg.reply(tr(msg.from_user.language_code, 'no_access'))
        return
    try:
        await bot.send_message(CHANNELS["vip"], tr("ru", "vip_send_check"))
        await msg.reply(tr(msg.from_user.language_code, 'sent_to_vip'))
    except Exception as e:
        print(f"❌ Ошибка при отправке в VIP: {e}")

@dp.message(Command("delete_post"))
async def delete_post_cmd(msg: Message):
    lang = msg.from_user.language_code
    if msg.from_user.id not in ADMINS:
        await msg.reply(tr(lang, 'admin_delete_only'))
        return

    parts = msg.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await msg.reply(tr(lang, 'delete_usage'))
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
        print(f"❌ Ошибка удаления: {e}")

if __name__ == "__main__":
    asyncio.run(main())
