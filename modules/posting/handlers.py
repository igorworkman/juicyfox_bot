# modules/posting/handlers.py
from __future__ import annotations

import os
import time
import logging
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
# REGION AI: imports
# fix: correct localization call for post plan button
from modules.common import i18n
from shared.utils.lang import get_lang
import hashlib
from shared import db
# END REGION AI

router = Router()
log = logging.getLogger("juicyfox.posting.ui")

# ── ENV ─────────────────────────────────────────────────────────────────────────
POST_PLAN_GROUP_ID = int(os.getenv("POST_PLAN_GROUP_ID", "0"))  # где планируем
LIFE_CHANNEL_ID    = int(os.getenv("LIFE_CHANNEL_ID", "0"))     # основной канал
VIP_CHANNEL_ID     = int(os.getenv("VIP_CHANNEL_ID", "0"))
LOG_CHANNEL_ID     = int(os.getenv("LOG_CHANNEL_ID", "0"))

# ── FSM ─────────────────────────────────────────────────────────────────────────
class PostPlan(StatesGroup):
    waiting_time   = State()
    choosing_target = State()
    waiting_content = State()

# ── helpers ─────────────────────────────────────────────────────────────────────
def _parse_time(s: str) -> Optional[int]:
    """
    Принимает: "YYYY-MM-DD HH:MM" ИЛИ "HH:MM" (сегодня), ИЛИ "now", ИЛИ "+30m/+2h".
    Возвращает UNIX-ts (UTC) или None.
    """
    s = s.strip().lower()
    now = int(time.time())

    if s == "now":
        return now
    if s.startswith("+") and s.endswith("m"):
        try: return now + int(s[1:-1]) * 60
        except: return None
    if s.startswith("+") and s.endswith("h"):
        try: return now + int(s[1:-1]) * 3600
        except: return None

    # HH:MM (сегодня)
    if len(s) == 5 and s[2] == ":" and s[:2].isdigit() and s[3:].isdigit():
        h, m = int(s[:2]), int(s[3:])
        t = time.localtime(now)
        return int(time.mktime((t.tm_year, t.tm_mon, t.tm_mday, h, m, 0, t.tm_wday, t.tm_yday, t.tm_isdst)))

    # YYYY-MM-DD HH:MM
    try:
        date_part, time_part = s.split()
        y, M, d = map(int, date_part.split("-"))
        h, m = map(int, time_part.split(":"))
        return int(time.mktime((y, M, d, h, m, 0, -1, -1, -1)))
    except Exception:
        return None

def _target_kb() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    # REGION AI: broadcast only button
    kb.button(text="📤 Mailing by ID base", callback_data="post:target:broadcast")
    # END REGION AI
    kb.adjust(1)
    return kb

# ── хэндлеры ────────────────────────────────────────────────────────────────────
def _is_planner_chat(msg: Message) -> bool:
    return POST_PLAN_GROUP_ID and msg.chat.id == POST_PLAN_GROUP_ID

@router.message(Command("post"))
async def cmd_post(msg: Message, state: FSMContext):
    if msg.chat.type not in {"group", "supergroup"} or not _is_planner_chat(msg):
        return
    await state.clear()
    # REGION AI: english planning prompt
    await msg.reply(
        "🗓 Enter publication time in format `DD.MM.YYYY HH:MM`\n"
        "Например: `15.09.2025 19:00`",
        parse_mode=None,
    )
    # END REGION AI
    await state.set_state(PostPlan.waiting_time)

@router.message(PostPlan.waiting_time)
async def set_time(msg: Message, state: FSMContext):
    try:
        ts_struct = time.strptime((msg.text or "").strip(), "%d.%m.%Y %H:%M")
        ts = int(time.mktime(ts_struct))
    except Exception:
        await msg.reply("❌ Неверный формат. Пример: 15.09.2025 19:00")
        return
    if ts < int(time.time()):
        await msg.reply("❌ Указано прошедшее время. Попробуйте снова.")
        return
    await state.update_data(run_at=ts)
    await _finalize_post(msg.reply, msg.bot, state)

"""Handlers for post planning."""

# REGION AI: post planning callbacks
async def _finalize_post(send, bot, state):
    data = await state.get_data()
    channel = data.get("channel")
    if channel is None:
        msg_obj = getattr(send, "__self__", None)
        lang = get_lang(getattr(msg_obj, "from_user", None))
        await send(i18n.tr(lang, "post_channel_not_specified"))
        return
    if not data.get("type"):
        await send("Отправь содержимое поста (текст/фото/видео/документ со подписью).")
        await state.set_state(PostPlan.waiting_content)
        return

    run_at = int(data["run_at"])
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(run_at))

    if channel == "broadcast":
        try:
            users = await db.get_all_relay_users()
        except Exception:
            users = []
        if not users:
            await send("❌ Нет пользователей в ID‑базе для рассылки")
            return
        for u in users:
            job = {
                "chat_id": int(u["user_id"]),
                "type": data["type"],
                "file_id": data.get("file_id"),
                "text": data.get("caption"),
                "run_at": run_at,
            }
            job_id = await db.enqueue_mailing(job)
            if LOG_CHANNEL_ID:
                try:
                    await bot.send_message(
                        LOG_CHANNEL_ID,
                        f"[post] queued id={job_id} → chat_id={u['user_id']} at {when}",
                    )
                except Exception:
                    pass
        await state.clear()
        await send(f"✅ Пост поставлен в очередь для {len(users)} пользователей, время: {when}")
        return

    job = {
        "chat_id": channel,
        "type": data["type"],
        "file_id": data.get("file_id"),
        "text": data.get("caption"),
        "run_at": run_at,
    }
    job_id = await db.enqueue_mailing(job)
    await state.clear()
    await send(f"✅ Пост поставлен в очередь (id={job_id}), время: {when}")
    if LOG_CHANNEL_ID:
        try:
            await bot.send_message(LOG_CHANNEL_ID, f"[post] queued id={job_id} → chat_id={channel} at {when}")
        except Exception:
            pass

@router.callback_query(F.data.startswith("post:target:"), PostPlan.choosing_target)
async def choose_target_cb(cq: CallbackQuery, state: FSMContext):
    # REGION AI: handle only broadcast target
    val = cq.data.split("post:target:", 1)[1]
    if val != "broadcast":
        await cq.answer("Некорректная цель", show_alert=True)
        return
    await cq.answer()
    await state.update_data(channel="broadcast")
    await cq.message.edit_text(
        "🗓 Enter publication time in format `DD.MM.YYYY HH:MM`\n"
        "Например: `15.09.2025 19:00`",
        parse_mode=None,
    )
    await state.set_state(PostPlan.waiting_time)
    # END REGION AI

@router.message(F.photo | F.video | F.document | F.animation)
async def offer_post_plan(msg: Message):
    if not _is_planner_chat(msg): return
    # REGION AI: prioritize photos over image documents
    if msg.photo:
        fid = msg.photo[-1].file_id
    elif msg.document:
        if msg.document.mime_type and msg.document.mime_type.startswith("image/"):
            fid = msg.document.file_id
        else:
            return
    elif msg.video:
        fid = msg.video.file_id
    elif msg.animation:
        fid = msg.animation.file_id
    else:
        return
    # END REGION AI
    kb = InlineKeyboardBuilder()
    # REGION AI: safe callback data
    safe_fid = hashlib.sha256(fid.encode()).hexdigest()[:32]
    kb.button(text="POST PLAN", callback_data=f"post_plan:{safe_fid}")
    # END REGION AI
    # REGION AI: localized choose post plan with fallback
    text = i18n.tr(get_lang(msg.from_user), "choose_post_plan") or "Выберите действие"
    await msg.reply(text, reply_markup=kb.as_markup())
    # END REGION AI

# REGION AI: post plan callback prefix
@router.callback_query(F.data.startswith("post_plan:"))
# END REGION AI
async def post_plan_cb(cq: CallbackQuery, state: FSMContext):
    await cq.answer()
    # REGION AI: handle reply context
    src = cq.message.reply_to_message or cq.message
    # END REGION AI
    if src.photo:
        tp, fid, cap = "photo", src.photo[-1].file_id, src.caption
    elif src.document and src.document.mime_type and src.document.mime_type.startswith("image/"):
        tp, fid, cap = "photo", src.document.file_id, src.caption
    elif src.video:
        tp, fid, cap = "video", src.video.file_id, src.caption
    elif src.document:
        tp, fid, cap = "document", src.document.file_id, src.caption
    elif src.animation:
        tp, fid, cap = "animation", src.animation.file_id, src.caption
    else:
        return
    await state.clear()
    await state.update_data(type=tp, file_id=fid, caption=cap)
    await cq.message.answer("Выбери цель публикации:", reply_markup=_target_kb().as_markup())
    await state.set_state(PostPlan.choosing_target)
# END REGION AI
