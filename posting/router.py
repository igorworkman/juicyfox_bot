from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import Command
from datetime import datetime
import calendar
import time
import logging
import __main__ as main

router = Router(name="post")

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

def get_post_plan_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="👀 Life", callback_data="post_to:life")
    kb.button(text="💿 Luxury", callback_data="post_to:luxury")
    kb.button(text="👑 VIP", callback_data="post_to:vip")
    kb.adjust(1)
    return kb.as_markup()

post_plan_kb = get_post_plan_kb()

def kb_days(d: dict, lang: str):
    y, m, selected_day = d["y"], d["m"], d.get("d")
    cal = calendar.monthcalendar(y, m)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=f"{y}-{m:02d}", callback_data="noop"))
    for w in cal:
        row_buttons = []
        for x in w:
            text = " " if x == 0 else (f"[{x}]" if x == selected_day else str(x))
            callback_data = "noop" if x == 0 else f"d:{x}"
            row_buttons.append(InlineKeyboardButton(text=text, callback_data=callback_data))
        kb.row(*row_buttons)
    kb.row(InlineKeyboardButton(text=main.tr(lang, "dt_cancel"), callback_data="cancel"))
    return kb.as_markup()

def get_time_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for r in range(4):
        kb.row(
            *[
                InlineKeyboardButton(
                    text=main.tr(lang, "choose_time", time=f"{h:02d}:00"),
                    callback_data=f"h:{h}",
                )
                for h in range(r * 6, (r + 1) * 6)
            ]
        )
    kb.row(InlineKeyboardButton(text=main.tr(lang, "dt_cancel"), callback_data="cancel"))
    return kb.as_markup()

def kb_hours(d: dict, lang: str):
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
    kb.row(InlineKeyboardButton(text=main.tr(lang, "dt_cancel"), callback_data="cancel"))
    return kb.as_markup()

def kb_minutes(data: dict, lang: str):
    kb = InlineKeyboardBuilder()
    for m in [0, 15, 30, 45]:
        kb.button(text=f"{m:02d}", callback_data=f"mi:{m:02d}")
    kb.adjust(4)
    return kb.as_markup()

def stars_kb(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    stars_values = [50, 100, 200, 300, 400, 600, 800, 1000]
    for val in stars_values:
        builder.button(text=f"{val}⭐️", callback_data=f"stars:{val}")
    builder.button(text=main.tr(lang, 'free_label'), callback_data="stars:FREE")
    builder.adjust(4)
    return builder.as_markup()

def done_kb(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=main.tr(lang, 'done_label'), callback_data='post_done')
    return b.as_markup()

@router.message(F.chat.id == main.POST_PLAN_GROUP_ID)
async def add_post_plan_button(msg: Message):
    if msg.from_user.id not in main.ADMINS:
        return
    if msg.media_group_id is not None:
        return
    if not (msg.photo or msg.video or msg.animation):
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📆 Post Plan", callback_data=f"start_post_plan:{msg.message_id}")]]
    )
    try:
        await msg.bot.send_message(
            msg.chat.id,
            f"Пост №{main.POST_COUNTER:03d}",
            reply_markup=kb,
            reply_to_message_id=msg.message_id,
        )
        main.POST_COUNTER += 1
    except Exception as e:
        logging.error(f"[POST_PLAN] Ошибка при добавлении кнопки: {e}")

@router.callback_query(F.data.startswith("start_post_plan:"))
async def start_post_plan(cq: CallbackQuery, state: FSMContext):
    if cq.message.chat.id != main.POST_PLAN_GROUP_ID:
        await cq.answer("⛔ Доступно только в постинг-группе", show_alert=True)
        return
    if cq.from_user.id not in main.ADMINS:
        await cq.answer("⛔ Только админы могут планировать посты", show_alert=True)
        return
    try:
        msg_id = int(cq.data.split(":")[1])
        await state.update_data(source_message_id=msg_id)
    except Exception as e:
        logging.error(f"[POST_PLAN] Ошибка парсинга message_id: {e}")
        return
    await state.set_state(Post.wait_channel)
    await cq.message.answer("Куда постить?", reply_markup=post_plan_kb)

@router.callback_query(F.data.startswith("post_to:"), Post.wait_channel)
async def post_choose_channel(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    channel = cq.data.split(":")[1]
    data_update = {"channel": channel}
    if channel != "life":
        data_update["tariff"] = main.CHANNEL_TARIFFS.get(channel, "")
    await state.update_data(**data_update)
    now = datetime.now()
    data = {"y": now.year, "m": now.month, "d": now.day, "h": now.hour, "mi": 0}
    await state.update_data(**data)
    await state.set_state(Post.select_datetime)
    await cq.message.edit_text(
        main.tr(cq.from_user.language_code, "dt_prompt"),
        reply_markup=kb_days(data, cq.from_user.language_code),
    )

@router.callback_query(Post.select_datetime, Post.wait_time, Post.wait_minute)
async def dt_callback(callback_query: CallbackQuery, state: FSMContext):
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
    elif act == 'h':
        h = int(val)
        await state.update_data(h=h)
        await state.set_state(Post.wait_minute)
        kb = kb_minutes(data, lang)
        await callback_query.message.edit_caption(
            caption=main.tr(lang, 'choose_minute'),
            reply_markup=kb,
        )
    elif act == 'mi':
        mi = int(val)
        await state.update_data(mi=mi)
        data = await state.get_data()
        ts = int(datetime(data['y'], data['m'], data['d'], data['h'], data['mi']).timestamp())
        channel = data.get("channel")
        await state.update_data(publish_ts=ts)
        if channel == "life":
            await state.set_state(Post.select_stars)
            await callback_query.message.edit_text(main.tr(lang, 'ask_stars'), reply_markup=stars_kb(lang))
        else:
            tariff = main.CHANNEL_TARIFFS.get(channel, "")
            await state.update_data(tariff=tariff)
            await state.set_state(Post.wait_content)
            await callback_query.message.edit_text(main.tr(lang, 'ask_content'), reply_markup=done_kb(lang))
    elif act == 'cancel':
        await callback_query.message.edit_text(main.tr(lang, 'cancel'))
        await state.clear()
    await callback_query.answer()

@router.callback_query(F.data.startswith("stars:"), Post.select_stars)
async def stars_selected(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    lang = cq.from_user.language_code
    val = cq.data.split(":")[1]
    tariff = "FREE" if val == "FREE" else f"{val} Stars⭐️"
    await state.update_data(tariff=tariff)
    await state.set_state(Post.wait_content)
    await cq.message.edit_text(main.tr(lang, 'ask_content'), reply_markup=done_kb(lang))

@router.message(Post.wait_description, F.chat.id == main.POST_PLAN_GROUP_ID)
async def post_description(msg: Message, state: FSMContext):
    lang = msg.from_user.language_code
    desc = msg.text or ''
    await state.update_data(description=desc)
    data = await state.get_data()
    if main.is_paid_channel(data.get('channel')):
        await state.update_data(price=None)
        await state.set_state(Post.wait_price)
        await msg.answer(main.tr(lang, 'set_price_prompt'))
    else:
        await state.set_state(Post.wait_content)
        await msg.answer(main.tr(lang, 'ask_content'), reply_markup=done_kb(lang))

@router.message(Post.wait_price, F.chat.id == main.POST_PLAN_GROUP_ID)
async def post_price(msg: Message, state: FSMContext):
    lang = msg.from_user.language_code
    await state.update_data(price=msg.text)
    await state.set_state(Post.wait_content)
    await msg.answer(main.tr(lang, 'ask_content'), reply_markup=done_kb(lang))

@router.message(Post.wait_content, F.chat.id == main.POST_PLAN_GROUP_ID)
async def post_content(msg: Message, state: FSMContext):
    data = await state.get_data()
    channel = data.get("channel")
    if not channel:
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
    elif msg.text:
        await state.update_data(text=msg.text)
        await msg.reply("Текст сохранён")

@router.callback_query(F.data == "post_done")
async def post_done(cq: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await cq.answer()
    channel = data["channel"]
    media_ids = ','.join(data.get("media_ids", []))
    text = data.get("text", "")
    source_msg_id = data.get("source_message_id", cq.message.message_id)
    ts = data["publish_ts"]
    rowid = await main._db_exec(
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
    lang = cq.from_user.language_code
    date_str = f"{data['d']:02d}.{data['m']:02d}.{data['y']}"
    time_str = f"{data['h']:02d}:{data['mi']:02d}"
    tariff_str = data["tariff"]
    await cq.message.edit_reply_markup()
    await cq.message.answer(
        main.tr(lang, 'post_scheduled').format(
            channel=channel.upper(),
            date=date_str,
            time=time_str,
            tariff=tariff_str,
        )
    )
    await state.clear()

@router.message(Command("delete_post"))
async def delete_post_cmd(msg: Message):
    lang = msg.from_user.language_code
    if msg.from_user.id not in main.ADMINS:
        await msg.reply("⛔️ Только админ может удалять посты.")
        return
    parts = msg.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await msg.reply("❌ Используй /delete_post <id>")
        return
    msg_id = int(parts[1])
    row = await main._db_exec(
        "SELECT chat_id FROM published_posts WHERE message_id = ?",
        (msg_id,),
        fetchone=True,
    )
    if not row:
        await msg.reply(main.tr(lang, 'error_post_not_found'))
        return
    chat_id = row[0]
    if chat_id not in [main.CHANNELS["vip"], main.LIFE_CHANNEL_ID, main.CHANNELS["luxury"]]:
        await msg.reply(main.tr(lang, 'not_allowed_channel'))
        return
    try:
        await msg.bot.delete_message(chat_id, msg_id)
        await msg.reply(main.tr(lang, 'post_deleted'))
    except Exception as e:
        logging.error(f"❌ Ошибка удаления: {e}")
