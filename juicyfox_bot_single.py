# JuicyFox Bot — single‑file (aiogram 3.20) + 30‑day access
# ---------------------------------------------------------
# • Club / VIP / Chat  → 8 валют → счёт → доступ ровно 30 суток
# • Donate             → валюта → сумма (USD) → счёт
# • Relay              → приват ↔ группа (CHAT_GROUP_ID)
# • RU/EN/ES UI           → auto by language_code

import os, logging, asyncio, httpx, time, aiosqlite
from typing import Dict, Any, Optional, Tuple
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

async def _init_db():
    async with aiosqlite.connect('messages.sqlite') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS messages(
              ts INTEGER,
              user_id INTEGER,
              msg_id INTEGER,
              is_reply INTEGER
            );
        ''')
        await db.commit()

asyncio.get_event_loop().run_until_complete(_init_db())

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ---------------- Config ----------------
TELEGRAM_TOKEN  = os.getenv('TELEGRAM_TOKEN')
CRYPTOBOT_TOKEN = os.getenv('CRYPTOBOT_TOKEN') or os.getenv('CRYPTO_BOT_TOKEN')
CHAT_GROUP_ID = int(os.getenv("CHAT_GROUP_ID", "-1002813332213"))
HISTORY_GROUP_ID = -1002721298286
ADMINS = [7893194894]
LIFE_CHANNEL_URL= os.getenv('LIFE_CHANNEL_URL', 'https://t.me/JuisyFoxOfficialLife')
API_BASE        = 'https://pay.crypt.bot/api'
VIP_CHANNEL_ID  = int(os.getenv('VIP_CHANNEL_ID', '-1001234567890'))  # приватный VIP‑канал
LUXURY_CHANNEL_ID = int(os.getenv('LUXURY_CHANNEL_ID', '-1002808420871'))
DB_PATH         = 'messages.sqlite'

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
    if user_id == 7893194894:
        return True
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
И я отвечу тебе уже сегодня 💌""",
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
  'consecutive_limit':'(3 из 3) — жду ответа от Juicy Fox. Вы сможете продолжить переписку через 18 часов или после ответа.',
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
 'vip_secret_desc': 'Твой личный доступ в VIP Secret от Juicy Fox 😈\n🔥Тут всё, о чём ты фантазировал:\n📸 больше HD фото нюдс крупным планом 🙈\n🎥 Видео, где я играю со своей киской 💦\n💬 Juicy Chat — где я отвечаю тебе лично, кружочками 😘\n📆 Период: 30 дней\n💸 Стоимость: 35$\n💳💵💱 — выбери, как тебе удобнее'
},
 'en':{
  'menu': """Hey, {name} 😘 I’m your Juicy Fox tonight 🦊
My 2 PRIVATE channels will drive you wild… 🔞💦🔥
Just you and me… Ready for some late-night fun? 💋
Open Juicy Chat 💬 — and I’ll be waiting inside 💌""",
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
  "vip_secret_desc": "Your personal access to Juicy Fox’s VIP Secret 😈\n🔥 Everything you've been fantasizing about:\n📸 More HD Photo close-up nudes 🙈\n🎥 Videos where I play with my pussy 💦\n💬 Juicy Chat — where I reply to you personally, with video-rols 😘\n📆 Duration: 30 days\n💸 Price: $35\n💳💵💱 — choose your preferred payment method"
 },
'es': {
  'menu': """Hola, {name} 😘 Esta noche soy tu Juicy Fox 🦊
Mis 2 canales PRIVADOS te van a enloquecer… 🔞💦🔥
Solo tú y yo… ¿Listo para jugar esta noche? 💋
Haz clic en Juicy Chat 💬 — y te espero adentro 💌""",
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
  'vip_secret_desc': "Tu acceso personal al VIP Secret de Juicy Fox 😈\n🔥 Todo lo que has estado fantaseando:\n📸 Más fotos HD de mis partes íntimas en primer plano 🙈\n🎥 Videos donde juego con mi Coño 💦\n💬 Juicy Chat — donde te respondo personalmente con videomensajes 😘\n📆 Duración: 30 días\n💸 Precio: 35$\n💳💵💱 — elige tu forma de pago preferida"
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
        tr(cq.from_user.language_code, 'life', life_link=LIFE_CHANNEL_URL),
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
    header = (f"[{msg.from_user.first_name}](tg://user?id={msg.from_user.id}) "
              f"• до {expires} • 💰 ${donated:.2f} • {flag}")

    header_msg = await bot.send_message(CHAT_GROUP_ID, header, parse_mode='Markdown')
    relay[header_msg.message_id] = msg.from_user.id
    cp = await bot.copy_message(CHAT_GROUP_ID, msg.chat.id, msg.message_id)
    relay[cp.message_id] = msg.from_user.id
    await _db_exec('INSERT INTO messages VALUES(?,?,?,?)', int(time.time()), msg.from_user.id, cp.message_id, 0)


    

# ---------------- Group → user relay ----------------------
@dp.message(F.chat.id == CHAT_GROUP_ID)
async def relay_group(msg: Message):
    if (msg.reply_to_message and
        msg.reply_to_message.message_id in relay):
        uid = relay[msg.reply_to_message.message_id]
        await bot.copy_message(uid, CHAT_GROUP_ID, msg.message_id)
        await _db_exec('INSERT INTO messages VALUES(?,?,?,?)', int(time.time()), uid, msg.message_id, 1)

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

    for ts, user_id, msg_id, is_reply in reversed(rows):
        try:
            await bot.copy_message(HISTORY_GROUP_ID, CHAT_GROUP_ID, msg_id)
        except Exception:
            await msg.reply(f"⚠️ Не удалось переслать msg_id={msg_id}")

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
