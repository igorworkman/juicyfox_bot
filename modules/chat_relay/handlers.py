# modules/chat_relay/handlers.py
from __future__ import annotations

import os
import logging
import time
from typing import Optional, Dict, Any, List

# REGION AI: imports
import asyncio
from aiogram.exceptions import TelegramNetworkError
try:
    from shared.db.repo import get_active_invoice, upsert_relay_user, get_relay_user
except Exception:  # pragma: no cover
    get_active_invoice = upsert_relay_user = get_relay_user = None  # type: ignore
# END REGION AI

from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

router = Router()
log = logging.getLogger("juicyfox.chat_relay")

# === Конфиг через ENV ===
RELAY_GROUP_ID = int(os.getenv("RELAY_GROUP_ID") or os.getenv("CHAT_GROUP_ID") or "0")
HISTORY_GROUP_ID = int(os.getenv("HISTORY_GROUP_ID") or "0")  # если задан — /history доступна только здесь
MODEL_NAME = os.getenv("MODEL_NAME", "Juicy Fox")
USER_STREAK_LIMIT = int(os.getenv("RELAY_STREAK_LIMIT", "3"))   # максимум входящих подряд без ответа
HISTORY_DEFAULT_N = int(os.getenv("RELAY_HISTORY_DEFAULT", "20"))

# === Асинхронный репозиторий (персистентный, если есть shared.db.repo; иначе — in-memory) ===
class _Repo:
    def __init__(self) -> None:
        self._mem_messages: Dict[int, List[Dict[str, Any]]] = {}
        self._streak: Dict[int, int] = {}
        try:
            from shared.db import repo as ext  # type: ignore
            self._ext = ext  # ожидаются async-функции
            log.info("chat_relay: using shared.db.repo backend")
        except Exception:
            self._ext = None
            log.info("chat_relay: using in-memory backend")

    # --- Счётчик подряд входящих сообщений ---
    async def inc_streak(self, user_id: int) -> int:
        if self._ext:
            try:
                return int(await self._ext.inc_streak(user_id))  # type: ignore
            except Exception as e:
                log.warning("repo.inc_streak failed, fallback: %s", e)
        self._streak[user_id] = self._streak.get(user_id, 0) + 1
        return self._streak[user_id]

    async def reset_streak(self, user_id: int) -> None:
        if self._ext:
            try:
                await self._ext.reset_streak(user_id)  # type: ignore
                return
            except Exception as e:
                log.warning("repo.reset_streak failed, fallback: %s", e)
        self._streak[user_id] = 0

    async def get_streak(self, user_id: int) -> int:
        if self._ext:
            try:
                return int(await self._ext.get_streak(user_id))  # type: ignore
            except Exception as e:
                log.warning("repo.get_streak failed, fallback: %s", e)
        return self._streak.get(user_id, 0)

    # --- История сообщений ---
    async def log_message(self, user_id: int, direction: str, content: Dict[str, Any]) -> None:
        if self._ext:
            try:
                await self._ext.log_message(user_id, direction, content)  # type: ignore
                return
            except Exception as e:
                log.warning("repo.log_message failed, fallback: %s", e)
        buf = self._mem_messages.setdefault(user_id, [])
        buf.append(content | {"direction": direction})

    async def get_history(self, user_id: int, limit: int) -> List[Dict[str, Any]]:
        if self._ext:
            try:
                return list(await self._ext.get_history(user_id, limit))  # type: ignore
            except Exception as e:
                log.warning("repo.get_history failed, fallback: %s", e)
        return list(self._mem_messages.get(user_id, []))[-limit:]


_repo = _Repo()


def _fmt_from(msg: Message) -> str:
    u = msg.from_user
    uid = u.id if u else "unknown"
    uname = f"@{u.username}" if u and u.username else ""
    name = f"{u.full_name}" if u else ""
    return f"from: {uid} {uname} {name}".strip()


def _now_ts() -> int:
    return int(time.time())


# REGION AI: media helpers
async def _send_with_retry(func, *args, **kwargs):
    for attempt in range(3):
        try:
            await func(*args, **kwargs)
            return
        except TelegramNetworkError as e:
            if attempt == 2:
                log.exception("relay to group failed: %s", e)
            else:
                await asyncio.sleep(1)
        except Exception as e:
            log.exception("relay to group failed: %s", e)
            return


async def _send_record(msg: Message, chat_id: int | None) -> Dict[str, Any]:
    header = _fmt_from(msg)
    text = (msg.text or msg.caption or "").strip()
    cap = f"{header}\n\n{text}" if text else header
    rec: Dict[str, Any] = {"type": msg.content_type, "ts": _now_ts()}

    def _run(func, *a, **k):
        if chat_id:
            asyncio.create_task(_send_with_retry(func, *a, **k))

    if msg.text:
        _run(msg.bot.send_message, chat_id, cap)
        rec["text"] = text
    elif msg.photo:
        _run(msg.bot.send_photo, chat_id, msg.photo[-1].file_id, caption=cap)
        rec.update(file_id=msg.photo[-1].file_id, text=text or None)
    elif msg.video:
        _run(msg.bot.send_video, chat_id, msg.video.file_id, caption=cap)
        rec.update(file_id=msg.video.file_id, text=text or None)
    elif msg.voice:
        _run(msg.bot.send_voice, chat_id, msg.voice.file_id, caption=cap)
        rec.update(file_id=msg.voice.file_id, text=text or None)
    elif msg.document:
        _run(msg.bot.send_document, chat_id, msg.document.file_id, caption=cap)
        rec.update(file_id=msg.document.file_id, text=text or None)
    elif msg.animation:
        _run(msg.bot.send_animation, chat_id, msg.animation.file_id, caption=cap)
        rec.update(file_id=msg.animation.file_id, text=text or None)
    elif msg.sticker:
        _run(msg.bot.send_sticker, chat_id, msg.sticker.file_id)
        rec.update(file_id=msg.sticker.file_id, text=msg.sticker.emoji or None)
    elif msg.video_note:
        _run(msg.bot.send_video_note, chat_id, msg.video_note.file_id)
        rec.update(file_id=msg.video_note.file_id, text=text or None)
    else:
        _run(msg.bot.send_message, chat_id, f"{header}\n\n[unsupported content]")
        rec["type"] = "unknown"

    return rec
# END REGION AI

# ========== Входящие от пользователя → в рабочую группу ==========
@router.message(F.chat.type == "private")
async def relay_incoming_to_group(msg: Message):
    """
    Любое личное сообщение, КРОМЕ команд, уходит в рабочую группу.
    Команды (начинаются с '/') игнорируются.
    """
    if not RELAY_GROUP_ID:
        return

    # Игнорируем команды вида "/start", "/help", "/..."
    if msg.text and msg.text.startswith("/"):
        return

    uid = msg.from_user.id
    if upsert_relay_user:
        await upsert_relay_user(uid, msg.from_user.username, msg.from_user.full_name)
        log.info("relay_users: upsert user_id=%s username=%s", uid, msg.from_user.username)

    # 1) Лимит подряд входящих
    streak = await _repo.inc_streak(uid)
    if streak > USER_STREAK_LIMIT:
        try:
            await msg.answer(f"Пожалуйста, дождись моего ответа 😘\nТвоё сообщение получено.\n— {MODEL_NAME}")
        except Exception:
            pass
        # REGION AI: log streaked message
        log_rec = await _send_record(msg, None)
        await _repo.log_message(uid, "in", log_rec)
        # END REGION AI
        return

    # 2) Пересылка в рабочую группу + лог
    try:
        # REGION AI: relay send
        log_rec = await _send_record(msg, RELAY_GROUP_ID)
        await _repo.log_message(uid, "in", log_rec)
        # END REGION AI
    except Exception as e:
        log.exception("relay to group failed: %s", e)


# REGION AI: auto relay from group
async def _safe_edit_text(msg: Message, text: str, reply_markup: Any = None) -> None:
    current_text = msg.text or ""
    if current_text == text and msg.reply_markup == reply_markup:
        return
    await msg.edit_text(text, reply_markup=reply_markup)

@router.message(F.chat.id == RELAY_GROUP_ID)
async def relay_from_group(msg: Message) -> None:
    if not msg.reply_to_message or (msg.text and msg.text.startswith("/")):
        return
    parts = (msg.reply_to_message.caption or msg.reply_to_message.text or "").split()
    if len(parts) < 2 or parts[0] != "from:" or not parts[1].isdigit():
        log.info("relay_from_group: cannot extract user_id, skipping.")
        return
    user_id = int(parts[1])
    log.info("relay_from_group: extracted user_id=%s from reply.", user_id)
    if get_relay_user:
        user = await get_relay_user(user_id)
        if not user:
            log.warning("relay_users: user_id not found in DB")
    else:
        # REGION AI: missing relay_users
        log.warning("relay_users: repository unavailable")
        # END REGION AI
    if get_active_invoice:
        try:
            invoice = await get_active_invoice(user_id)
        except Exception:
            invoice = None
        if not invoice:
            log.warning(
                "relay_from_group: missing user_id in DB, possibly after deploy reset."
            )
    try:
        # REGION AI: relay via copy_message
        await msg.bot.copy_message(user_id, msg.chat.id, msg.message_id)
        # fix: log media file_id for accurate history playback
        log_rec = {"type": msg.content_type, "ts": _now_ts()}
        caption = msg.caption or msg.text or None
        if msg.photo:
            log_rec.update({"file_id": msg.photo[-1].file_id, "text": caption})
        elif msg.video:
            log_rec.update({"file_id": msg.video.file_id, "text": caption})
        elif msg.voice:
            log_rec.update({"file_id": msg.voice.file_id, "text": caption})
        elif msg.document:
            log_rec.update({"file_id": msg.document.file_id, "text": caption})
        elif msg.animation:
            log_rec.update({"file_id": msg.animation.file_id, "text": caption})
        elif msg.sticker:
            log_rec.update({"file_id": msg.sticker.file_id, "text": msg.sticker.emoji})
        else:
            log_rec.update({"text": caption})
        await _repo.log_message(user_id, "out", log_rec)
        if msg.text:
            await _safe_edit_text(msg, msg.text, reply_markup=None)
        log.info(
            "relay_from_group: delivered to user_id=%s type=%s",
            user_id,
            msg.content_type,
        )
        # END REGION AI
    except Exception as e:
        log.error("relay_from_group: failed to deliver user_id=%s error=%s", user_id, e)
    finally:
        await _repo.reset_streak(user_id)
# END REGION AI
# ========== Ответ из рабочей группы пользователю ==========
@router.message(Command("r"))
async def reply_from_group(cmd: Message, command: CommandObject):
    """
    /r <user_id> <текст>  — отправить пользователю из группы
    Если это reply в группе, можно: ответить на сообщение и написать /r <текст>
    """
    if cmd.chat.type not in {"group", "supergroup"}:
        return

    args = (command.args or "").strip()
    reply_to: Optional[Message] = cmd.reply_to_message

    # Вариант 1: /r 12345 hello there
    if args:
        parts = args.split(maxsplit=1)
        if len(parts) == 2 and parts[0].isdigit():
            user_id = int(parts[0])
            text = parts[1]
            try:
                await cmd.bot.send_message(user_id, text)
                await _repo.log_message(user_id, "out", {"type": "text", "text": text, "ts": _now_ts()})
                await cmd.reply("✅ Отправлено")
            finally:
                # даже если отправка упала — сбрасываем счётчик, чтобы не копился
                await _repo.reset_streak(user_id)
            return

    # Вариант 2: reply на системное сообщение + /r текст
    if reply_to and args:
        lines = (reply_to.caption or reply_to.text or "").splitlines()
        if lines and lines[0].startswith("from:"):
            try:
                user_id = int(lines[0].split()[1])
                try:
                    await cmd.bot.send_message(user_id, args)
                    await _repo.log_message(user_id, "out", {"type": "text", "text": args, "ts": _now_ts()})
                    await cmd.reply("✅ Отправлено")
                finally:
                    await _repo.reset_streak(user_id)
                return
            except Exception:
                pass

    await cmd.reply("❓ Использование: /r <user_id> <текст>\nили ответьте на сообщение пользователя командой /r <текст>")


# ========== История ==========
@router.message(Command("history"))
async def history_cmd(m: Message, command: CommandObject):
    """
    /history <user_id> [N]
    Если задан HISTORY_GROUP_ID — команда доступна только там.
    """
    if m.chat.type not in {"group", "supergroup"}:
        return
    if HISTORY_GROUP_ID and m.chat.id != HISTORY_GROUP_ID:
        return  # тихо игнорируем вне спец-группы

    args = (command.args or "").split()
    if not args or not args[0].isdigit():
        await m.reply("Использование: /history <user_id> [N]")
        return
    user_id = int(args[0])
    try:
        limit = int(args[1]) if len(args) > 1 else HISTORY_DEFAULT_N
    except Exception:
        limit = HISTORY_DEFAULT_N

    messages = await _repo.get_history(user_id, limit)
    if not messages:
        await m.reply("История пуста.")
        return

    # Формат: «hh:mm in/out [type] текст/файл (усечён)»
    def _fmt_msg(rec: Dict[str, Any]) -> str:
        t = time.strftime("%H:%M", time.localtime(rec.get("ts", _now_ts())))
        direction = rec.get("direction", "?")
        typ = rec.get("type", "text")
        text = (rec.get("text") or rec.get("file_id") or "").replace("\n", " ")
        if len(text) > 64:
            text = text[:60] + "…"
        return f"{t} {direction:<3} [{typ}] {text}"

    chunk = "\n".join(_fmt_msg(r) for r in messages[-limit:])
    await m.reply(f"История {user_id} (последние {limit}):\n{chunk}")
