# modules/posting/handlers.py
from __future__ import annotations

import os
import time
import logging
from typing import Any, Dict, Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()
log = logging.getLogger("juicyfox.posting.ui")

# ── ENV ─────────────────────────────────────────────────────────────────────────
POST_PLAN_GROUP_ID = int(os.getenv("POST_PLAN_GROUP_ID", "0"))     # где планируем
DEFAULT_TARGET_ID  = int(os.getenv("LIFE_CHANNEL_ID", "0"))        # куда постим по умолчанию
VIP_CHANNEL_ID     = int(os.getenv("VIP_CHANNEL_ID", "0"))
LOG_CHANNEL_ID     = int(os.getenv("LOG_CHANNEL_ID", "0"))
DB_PATH            = os.getenv("DB_PATH", "/app/data/juicyfox.sqlite")

# ── репозиторий: shared.db.repo если есть; иначе локальная таблица post_queue ──
try:
    from shared.db import repo as db  # type: ignore
    _HAS_SHARED_REPO = True
except Exception:
    _HAS_SHARED_REPO = False

async def _ensure_local_table():
    if _HAS_SHARED_REPO:
        return
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS post_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                text TEXT,
                file_id TEXT,
                run_at INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                retries INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await conn.commit()

async def _enqueue_post(job: Dict[str, Any]) -> int:
    """
    job: {chat_id, type, text?, file_id?, run_at}
    return: job_id
    """
    if _HAS_SHARED_REPO and hasattr(db, "enqueue_post"):
        return await db.enqueue_post(job)  # type: ignore

    # локальный fallback
    await _ensure_local_table()
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "INSERT INTO post_queue(chat_id, type, text, file_id, run_at) VALUES (?,?,?,?,?)",
            (int(job["chat_id"]), job["type"], job.get("text"), job.get("file_id"), int(job["run_at"]))
        )
        await conn.commit()
        return int(cur.lastrowid)

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

def _targets_kb() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    if DEFAULT_TARGET_ID:
        kb.button(text="Основной канал", callback_data=f"post:target:{DEFAULT_TARGET_ID}")
    if VIP_CHANNEL_ID:
        kb.button(text="VIP канал", callback_data=f"post:target:{VIP_CHANNEL_ID}")
    kb.button(text="Другое (введите ID)", callback_data="post:target:other")
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
    await msg.reply(
        "🗓 Укажи время публикации:\n"
        "• `now` — сразу\n"
        "• `HH:MM` — сегодня в указанное время\n"
        "• `YYYY-MM-DD HH:MM`\n"
        "• `+30m`, `+2h`",
        parse_mode=None,
    )
    await state.set_state(PostPlan.waiting_time)

@router.message(PostPlan.waiting_time)
async def set_time(msg: Message, state: FSMContext):
    ts = _parse_time(msg.text or "")
    if not ts or ts < int(time.time()) - 30:
        await msg.reply("⏰ Не понял время. Пример: `now`, `14:30`, `2025-08-30 20:00`, `+45m`.")
        return
    await state.update_data(run_at=ts)
    await msg.reply("Выбери цель публикации или введи chat_id числом:", reply_markup=_targets_kb().as_markup())
    await state.set_state(PostPlan.choosing_target)

@router.callback_query(F.data.startswith("post:target:"), PostPlan.choosing_target)
async def choose_target_cb(cq: CallbackQuery, state: FSMContext):
    _, _, val = cq.data.partition("post:target:")
    if val == "other":
        await cq.message.edit_text("Введи числовой chat_id (пример: -1001234567890):")
        return
    try:
        chat_id = int(val)
    except Exception:
        await cq.answer("Некорректный chat_id", show_alert=True)
        return
    await state.update_data(chat_id=chat_id)
    await cq.message.edit_text("Отправь содержимое поста (текст/фото/видео/документ со подписью).")
    await state.set_state(PostPlan.waiting_content)

@router.message(PostPlan.choosing_target)
async def choose_target_text(msg: Message, state: FSMContext):
    try:
        chat_id = int(msg.text.strip())
    except Exception:
        await msg.reply("Это не похоже на chat_id. Попробуй ещё раз или нажми кнопку.")
        return
    await state.update_data(chat_id=chat_id)
    await msg.reply("Отправь содержимое поста (текст/фото/видео/документ со подписью).")
    await state.set_state(PostPlan.waiting_content)

@router.message(PostPlan.waiting_content)
async def receive_content(msg: Message, state: FSMContext):
    data = await state.get_data()
    run_at = int(data.get("run_at", 0))
    chat_id = int(data.get("chat_id", 0))
    if not run_at or not chat_id:
        await msg.reply("Что-то пошло не так. Начни заново: /post")
        await state.clear()
        return

    job: Dict[str, Any]
    if msg.text:
        job = {"chat_id": chat_id, "type": "text", "text": msg.text, "run_at": run_at}
    elif msg.photo:
        job = {"chat_id": chat_id, "type": "photo", "file_id": msg.photo[-1].file_id, "text": msg.caption, "run_at": run_at}
    elif msg.video:
        job = {"chat_id": chat_id, "type": "video", "file_id": msg.video.file_id, "text": msg.caption, "run_at": run_at}
    elif msg.document:
        job = {"chat_id": chat_id, "type": "document", "file_id": msg.document.file_id, "text": msg.caption, "run_at": run_at}
    elif msg.animation:
        job = {"chat_id": chat_id, "type": "animation", "file_id": msg.animation.file_id, "text": msg.caption, "run_at": run_at}
    else:
        await msg.reply("Этот тип контента пока не поддержан. Пришли текст/фото/видео/документ.")
        return

    job_id = await _enqueue_post(job)
    await state.clear()
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(run_at))
    await msg.reply(f"✅ Пост поставлен в очередь (id={job_id}), время: {when}")

    # Лог каналу (если задан)
    if LOG_CHANNEL_ID:
        try:
            await msg.bot.send_message(LOG_CHANNEL_ID, f"[post] queued id={job_id} → chat_id={chat_id} at {when}")
        except Exception:
            pass
