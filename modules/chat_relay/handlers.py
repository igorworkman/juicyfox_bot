# modules/chat_relay/handlers.py
from __future__ import annotations

import os
import logging
import time
from typing import Optional, Dict, Any, List

# REGION AI: imports
import asyncio
from aiogram.exceptions import TelegramNetworkError
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


# ========== Входящие от пользователя → в рабочую группу ==========
@router.message(F.chat.type == "private")
async def relay_incoming_to_group(msg: Message):
    """
    Любое личное сообщение, КРОМЕ команд, уходит в рабочую группу.
    Команды (начинаются с '/') игнорируются.
    """
    if not RELAY_GROUP_ID:
        return

    # REGION AI: retry helper
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
    # END REGION AI

    # Игнорируем команды вида "/start", "/help", "/..."
    if msg.text and msg.text.startswith("/"):
        return

    uid = msg.from_user.id
    caption_header = _fmt_from(msg)
    # Поддержка "медиа + подпись": текст берём из msg.text ИЛИ msg.caption
    content_text = (msg.text or msg.caption or "").strip()

    # 1) Лимит подряд входящих
    streak = await _repo.inc_streak(uid)
    if streak > USER_STREAK_LIMIT:
        try:
            await msg.answer(f"Пожалуйста, дождись моего ответа 😘\nТвоё сообщение получено.\n— {MODEL_NAME}")
        except Exception:
            pass
        # историю всё равно логируем, но в группу не шлём, чтобы не спамить
        await _repo.log_message(uid, "in", {
            "type": "text" if msg.text else "media",
            "text": content_text or None,
            "ts": _now_ts()
        })
        return

    # 2) Пересылка в рабочую группу + лог
    try:
        sent = False
        if msg.text:
            # REGION AI: relay send text
            asyncio.create_task(_send_with_retry(msg.bot.send_message, RELAY_GROUP_ID, f"{caption_header}\n\n{content_text}"))
            # END REGION AI
            sent = True
            await _repo.log_message(uid, "in", {"type": "text", "text": content_text, "ts": _now_ts()})

        elif msg.photo:
            cap = f"{caption_header}\n\n{content_text}" if content_text else caption_header
            # REGION AI: relay send photo
            asyncio.create_task(_send_with_retry(msg.bot.send_photo, RELAY_GROUP_ID, msg.photo[-1].file_id, caption=cap))
            # END REGION AI
            sent = True
            await _repo.log_message(uid, "in", {"type": "photo", "file_id": msg.photo[-1].file_id, "text": content_text or None, "ts": _now_ts()})

        elif msg.video:
            cap = f"{caption_header}\n\n{content_text}" if content_text else caption_header
            # REGION AI: relay send video
            asyncio.create_task(_send_with_retry(msg.bot.send_video, RELAY_GROUP_ID, msg.video.file_id, caption=cap))
            # END REGION AI
            sent = True
            await _repo.log_message(uid, "in", {"type": "video", "file_id": msg.video.file_id, "text": content_text or None, "ts": _now_ts()})

        elif msg.voice:
            cap = f"{caption_header}\n\n{content_text}" if content_text else caption_header
            # REGION AI: relay send voice
            asyncio.create_task(_send_with_retry(msg.bot.send_voice, RELAY_GROUP_ID, msg.voice.file_id, caption=cap))
            # END REGION AI
            sent = True
            await _repo.log_message(uid, "in", {"type": "voice", "file_id": msg.voice.file_id, "text": content_text or None, "ts": _now_ts()})

        elif msg.document:
            cap = f"{caption_header}\n\n{content_text}" if content_text else caption_header
            # REGION AI: relay send document
            asyncio.create_task(_send_with_retry(msg.bot.send_document, RELAY_GROUP_ID, msg.document.file_id, caption=cap))
            # END REGION AI
            sent = True
            await _repo.log_message(uid, "in", {"type": "document", "file_id": msg.document.file_id, "text": content_text or None, "ts": _now_ts()})

        elif msg.animation:
            cap = f"{caption_header}\n\n{content_text}" if content_text else caption_header
            # REGION AI: relay send animation
            asyncio.create_task(_send_with_retry(msg.bot.send_animation, RELAY_GROUP_ID, msg.animation.file_id, caption=cap))
            # END REGION AI
            sent = True
            await _repo.log_message(uid, "in", {"type": "animation", "file_id": msg.animation.file_id, "text": content_text or None, "ts": _now_ts()})

        elif msg.sticker:
            # REGION AI: relay send sticker
            asyncio.create_task(_send_with_retry(msg.bot.send_message, RELAY_GROUP_ID, f"{caption_header}\n\n[sticker] {msg.sticker.emoji or ''}".strip()))
            # END REGION AI
            sent = True
            await _repo.log_message(uid, "in", {"type": "sticker", "text": msg.sticker.emoji or None, "ts": _now_ts()})

        if not sent:
            # REGION AI: relay send unknown
            asyncio.create_task(_send_with_retry(msg.bot.send_message, RELAY_GROUP_ID, f"{caption_header}\n\n[unsupported content]"))
            # END REGION AI
            await _repo.log_message(uid, "in", {"type": "unknown", "ts": _now_ts()})

    except Exception as e:
        log.exception("relay to group failed: %s", e)


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
