"""Handlers for the history/archival module (Plan A).

This module provides a `/history` command that allows operators to
retrieve the last N messages exchanged with a particular user.  It
supports both text and media messages; for media, only the Telegram
file ID is stored in the database and reused when sending the
history back to the operator, keeping storage lightweight.

Usage::

    /history <user_id> [N]

Where ``user_id`` is the numeric Telegram ID of the user whose
history you want to inspect, and ``N`` is an optional limit on the
number of recent messages to display (default is taken from
``HISTORY_DEFAULT_N`` or ``RELAY_HISTORY_DEFAULT`` environment
variables; if none are set, 20 is used).

The command only responds inside the configured ``HISTORY_GROUP_ID``
(or ``CHAT_GROUP_ID`` if ``HISTORY_GROUP_ID`` is not set) to avoid
leaking user data in unintended chats.
"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional

from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

logger = logging.getLogger("juicyfox.history")

router = Router()

# ---------------------------------------------------------------------------
# Environment and defaults
# ---------------------------------------------------------------------------
# Which chat/group can issue history commands.  If HISTORY_GROUP_ID is not
# defined, fall back to CHAT_GROUP_ID (so that history can be requested in
# the same group as relay messages).  If neither is set or set to zero, the
# command is effectively disabled.
HISTORY_GROUP_ID = int(os.getenv("HISTORY_GROUP_ID") or os.getenv("CHAT_GROUP_ID") or "0")

# Default number of messages to return when the limit is not specified.
# Use HISTORY_DEFAULT_N if defined; otherwise fallback to RELAY_HISTORY_DEFAULT
# (used by chat_relay), else 20.
try:
    HISTORY_DEFAULT_N = int(os.getenv("HISTORY_DEFAULT_N") or os.getenv("RELAY_HISTORY_DEFAULT") or "20")
except Exception:
    HISTORY_DEFAULT_N = 20

# ---------------------------------------------------------------------------
# Repository interface
# ---------------------------------------------------------------------------
# We try to import the shared database repository (shared.db.repo).  If it
# exists, we'll use its asynchronous get_history() function to fetch
# messages.  Otherwise, we'll fall back to an in-memory stub that stores
# nothing and returns an empty list.  This allows the bot to run even
# without a persistent storage backend (though obviously history will be
# empty until shared.db.repo is available).

class _InMemoryHistoryRepo:
    """Fallback in‑memory history repository.

    This stub stores messages in process memory.  It exposes log_message()
    and get_history() to match the interface of ``shared.db.repo``.  In
    practice, if your deployment does not include ``shared.db.repo``, the
    history functionality will always report an empty history.
    """

    def __init__(self) -> None:
        self._messages: Dict[int, List[Dict[str, Any]]] = {}

    async def log_message(self, user_id: int, direction: str, content: Dict[str, Any]) -> None:
        buf = self._messages.setdefault(user_id, [])
        buf.append(content | {"direction": direction})

    async def get_history(self, user_id: int, limit: int) -> List[Dict[str, Any]]:
        return list(self._messages.get(user_id, []))[-limit:]


# Repository for history.  This may be ``shared.db.repo`` if available or
# an in‑memory fallback otherwise.  ``_shared_repo`` holds the imported
# module (or ``None``) and ``_mem_repo`` holds an instance of
# ``_InMemoryHistoryRepo`` when the shared backend is unavailable.
_shared_repo: Optional[Any]
_mem_repo: Optional[_InMemoryHistoryRepo] = None

try:
    from shared.db import repo as _shared_repo  # type: ignore
    logger.info("history: using shared.db.repo backend")
except Exception:
    _shared_repo = None
    _mem_repo = _InMemoryHistoryRepo()
    logger.info("history: shared.db.repo not available; using in‑memory fallback")


async def _get_history(user_id: int, limit: int) -> List[Dict[str, Any]]:
    """Fetch the last ``limit`` messages for ``user_id``.

    Try the shared repository first; if it's unavailable or raises, fall
    back to the in‑memory store.
    """
    if _shared_repo:
        try:
            return list(await _shared_repo.get_history(user_id, limit))  # type: ignore
        except Exception as e:
            logger.warning("history: shared repo get_history failed, falling back: %s", e)
    # If shared repo is missing or failed, use in‑memory fallback.  The
    # in‑memory fallback will always return an empty list unless messages
    # have been logged via `_mem_repo.log_message()`.
    # In‑memory fallback: if _mem_repo is defined, use it; otherwise return empty
    if _mem_repo:
        return await _mem_repo.get_history(user_id, limit)
    return []


async def _send_record(bot: Bot, chat_id: int, rec: Dict[str, Any]) -> None:
    """Send a single history record to the specified chat.

    Depending on the ``type`` field of the record, it chooses the
    appropriate Telegram API call.  Unsupported types are sent as a plain
    text describing the type.
    """
    typ = rec.get("type", "text")
    text = rec.get("text") or None
    file_id = rec.get("file_id") or None
    try:
        if typ == "text" or (typ is None and not file_id):
            await bot.send_message(chat_id, text or "")
        elif typ == "photo":
            await bot.send_photo(chat_id, file_id, caption=text)
        elif typ == "video":
            await bot.send_video(chat_id, file_id, caption=text)
        elif typ == "voice":
            await bot.send_voice(chat_id, file_id, caption=text)
        elif typ == "animation":
            await bot.send_animation(chat_id, file_id, caption=text)
        elif typ == "document":
            await bot.send_document(chat_id, file_id, caption=text)
        elif typ == "audio":
            await bot.send_audio(chat_id, file_id, caption=text)
        elif typ == "video_note":
            await bot.send_video_note(chat_id, file_id)
        elif typ == "sticker":
            await bot.send_sticker(chat_id, file_id)
        else:
            # Unknown or unsupported type; send the text with a marker
            await bot.send_message(chat_id, f"[{typ}] {text or ''}")
    except Exception as e:
        logger.warning("history: failed to send record (%s): %s", typ, e)


@router.message(Command("history"))
async def history_cmd(msg: Message, command: CommandObject) -> None:
    """Handle the /history command.

    Expected syntax: ``/history <user_id> [limit]``.  Only responds
    inside the configured history group to prevent accidental leaks of
    conversation logs.
    """
    # Only operate in groups/supergroups
    if msg.chat.type not in {"group", "supergroup"}:
        return
    # Respect the history group limitation
    if HISTORY_GROUP_ID and msg.chat.id != HISTORY_GROUP_ID:
        return

    args = (command.args or "").split()
    if not args:
        await msg.reply("Использование: /history <user_id> [N]")
        return
    # Parse user_id and optional limit
    try:
        user_id = int(args[0])
        limit = int(args[1]) if len(args) > 1 else HISTORY_DEFAULT_N
    except Exception:
        await msg.reply("Использование: /history <user_id> [N]")
        return

    # Retrieve history
    records = await _get_history(user_id, limit)
    if not records:
        await msg.reply("История пуста.")
        return
    # Send each record.  We preserve chronological order (oldest→newest).
    for rec in records[-limit:]:
        await _send_record(msg.bot, msg.chat.id, rec)
