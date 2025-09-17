# modules/chat_relay/handlers.py
from __future__ import annotations

import os
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

# REGION AI: imports
from modules.common.i18n import tr
from shared.utils.lang import get_lang
from shared.utils.telegram import send_with_retry
from modules.ui_membership.keyboards import vip_currency_kb
from modules.constants.paths import VIP_PHOTO
try:
    from shared.db.repo import (
        get_active_invoice,
        upsert_relay_user,
        get_relay_user,
        link_user_group,
        get_group_for_user,
        get_user_by_group,
        get_chat_number,
        get_user_profile,
    )
except Exception:  # pragma: no cover
    (
        get_active_invoice,
        upsert_relay_user,
        get_relay_user,
        link_user_group,
        get_group_for_user,
        get_user_by_group,
        get_chat_number,
        get_user_profile,
    ) = (None, None, None, None, None, None, None, None)  # type: ignore
try:
    from shared.config.env import config
except Exception:  # pragma: no cover
    config = None  # type: ignore
# END REGION AI

from aiogram import Router, F  # noqa: E402
from aiogram.filters import Command, CommandObject  # noqa: E402
from aiogram.types import Message, FSInputFile  # noqa: E402

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


# REGION AI: extended header
def _fmt_from(msg: Message) -> str:
    u = msg.from_user
    uid = u.id if u else "unknown"
    lang = (u.language_code or "")[:2] if u else ""
    flag = (
        "".join(chr(ord(c.upper()) + 127397) for c in lang)
        if len(lang) == 2
        else ""
    )
    if lang == "en":
        flag = "🇺🇸 EN"
    chat_num = None
    if isinstance(uid, int):
        try:
            total, until_ts = get_user_profile(uid) if get_user_profile else (0.0, None)
            chat_num = get_chat_number(uid) if get_chat_number else None
        except Exception:  # pragma: no cover
            total, until_ts = (0.0, None)
            chat_num = None
    else:
        total, until_ts = (0.0, None)
        chat_num = None

    if chat_num is not None:
        parts = [f"№{chat_num}", str(uid)]
        if u and u.username:
            parts.append(f"@{u.username}")
        if u and u.full_name:
            parts.append(u.full_name)
    else:
        parts = [f"from: {uid}"]
        display = (u.full_name or u.username) if u else None
        if display:
            parts.append(display)
        if u and u.username:
            parts.append(f"@{u.username}")

    if flag:
        parts.append(flag)

    parts.append(f"💰 ${total:.2f}")

    if until_ts:
        parts.append(time.strftime("до %Y-%m-%d", time.localtime(until_ts)))

    return " • ".join(parts)
# END REGION AI


def _now_ts() -> int:
    return int(time.time())


async def _chat_subscription_active(user_id: int) -> bool:
    """Return ``True`` when the latest chat grant is still valid."""

    if user_id <= 0:
        return False

    repo_backend = getattr(_repo, "_ext", None)
    until_ts: Optional[int] = None
    checked = False
    if repo_backend:
        try:
            async with repo_backend._db() as db:  # type: ignore[attr-defined]
                cur = await db.execute(
                    """
                    SELECT until_ts
                    FROM access_grants
                    WHERE user_id=? AND plan_code LIKE 'chat_%'
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """,
                    (user_id,),
                )
                row = await cur.fetchone()
                checked = True
                if row and row[0] is not None:
                    until_ts = int(row[0])
        except Exception as e:  # pragma: no cover - degrade gracefully
            log.warning(
                "chat_relay: failed to check chat access for user_id=%s: %s",
                user_id,
                e,
            )

    if until_ts is None and get_user_profile:
        try:
            _, until = get_user_profile(user_id)
            if until is not None:
                until_ts = int(until)
            checked = True
        except Exception:  # pragma: no cover
            return True
    if until_ts is None:
        return not checked
    try:
        expires_at = datetime.fromtimestamp(int(until_ts), tz=timezone.utc)
    except Exception:
        log.warning(
            "chat_relay: invalid until_ts=%r for user_id=%s", until_ts, user_id
        )
        return False

    return expires_at >= datetime.now(timezone.utc)


async def _send_record(msg: Message, chat_id: int, header: Optional[str] | None = None) -> None:
    header = header or _fmt_from(msg)
    text = (msg.text or msg.caption or "").strip()
    bot = msg.bot
    rec = {"type": msg.content_type, "ts": _now_ts()}
    media_id: Optional[str] = None

    if msg.text:
        await send_with_retry(
            bot.send_message,
            chat_id,
            f"{header}\n\n{text}",
            logger=log,
        )
        rec["text"] = text
    elif msg.photo:
        media_id = msg.photo[-1].file_id
        cap = f"{header}\n\n{text}" if text else header
        await send_with_retry(
            bot.send_photo,
            chat_id,
            media_id,
            caption=cap,
            logger=log,
        )
        rec.update({"file_id": media_id, "text": text or None})
    elif msg.video:
        media_id = msg.video.file_id
        cap = f"{header}\n\n{text}" if text else header
        await send_with_retry(
            bot.send_video,
            chat_id,
            media_id,
            caption=cap,
            logger=log,
        )
        rec.update({"file_id": media_id, "text": text or None})
    elif msg.voice:
        media_id = msg.voice.file_id
        cap = f"{header}\n\n{text}" if text else header
        await send_with_retry(
            bot.send_voice,
            chat_id,
            media_id,
            caption=cap,
            logger=log,
        )
        rec.update({"file_id": media_id, "text": text or None})
    elif msg.document:
        media_id = msg.document.file_id
        cap = f"{header}\n\n{text}" if text else header
        await send_with_retry(
            bot.send_document,
            chat_id,
            media_id,
            caption=cap,
            logger=log,
        )
        rec.update({"file_id": media_id, "text": text or None})
    elif msg.animation:
        media_id = msg.animation.file_id
        cap = f"{header}\n\n{text}" if text else header
        await send_with_retry(
            bot.send_animation,
            chat_id,
            media_id,
            caption=cap,
            logger=log,
        )
        rec.update({"file_id": media_id, "text": text or None})
    elif msg.sticker:
        media_id = msg.sticker.file_id
        await send_with_retry(bot.send_message, chat_id, header, logger=log)
        await send_with_retry(bot.send_sticker, chat_id, media_id, logger=log)
        rec.update({"file_id": media_id, "text": msg.sticker.emoji or None})
    elif msg.video_note:
        media_id = msg.video_note.file_id
        await send_with_retry(bot.send_message, chat_id, header, logger=log)
        await send_with_retry(bot.send_video_note, chat_id, media_id, logger=log)
        rec["file_id"] = media_id
    else:
        await send_with_retry(
            bot.send_message,
            chat_id,
            f"{header}\n\n[unsupported content]",
            logger=log,
        )
        rec["type"] = "unknown"

    await _repo.log_message(msg.from_user.id, "in", rec)


# END REGION AI

# REGION AI: vip club handler
@router.message(
    F.chat.type == "private",
    F.text.startswith("/vip") | F.text.startswith("VIP CLUB"),
)
async def vip_club(msg: Message) -> None:
    lang = get_lang(msg.from_user)
    if VIP_PHOTO.exists():
        photo = FSInputFile(VIP_PHOTO)
        await send_with_retry(
            msg.answer_photo,
            photo,
            caption=tr(lang, "vip_club_description"),
            reply_markup=vip_currency_kb(lang),
            parse_mode="HTML",
            logger=log,
        )
    else:
        await send_with_retry(
            msg.answer,
            tr(lang, "vip_club_description"),
            reply_markup=vip_currency_kb(lang),
            parse_mode="HTML",
            logger=log,
        )


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
    caption_header = _fmt_from(msg)
    # Поддержка "медиа + подпись": текст берём из msg.text ИЛИ msg.caption
    content_text = (msg.text or msg.caption or "").strip()
    incoming_log = {
        "type": "text" if msg.text else "media",
        "text": content_text or None,
        "ts": _now_ts(),
    }
    status = "active"
    try:
        from shared.db.repo import get_user_status  # type: ignore
        status = await get_user_status(uid) or "active"
    except Exception:
        pass
    if status != "active":
        try:
            lang = get_lang(msg.from_user)
            await send_with_retry(
                msg.answer,
                tr(lang, "subscription_expired"),
                logger=log,
            )
        except Exception:
            pass
        await _repo.log_message(
            uid,
            "in",
            incoming_log,
        )
        return

    if not await _chat_subscription_active(uid):
        try:
            lang = get_lang(msg.from_user)
            await send_with_retry(
                msg.answer,
                tr(lang, "chat_not_active"),
                logger=log,
            )
        except Exception:
            pass
        await _repo.log_message(uid, "in", incoming_log)
        log.info("chat_relay: inactive chat subscription, skip relay for user_id=%s", uid)
        return

    group_id = RELAY_GROUP_ID
    if get_group_for_user:
        try:
            group_id = int(await get_group_for_user(uid) or RELAY_GROUP_ID)
        except Exception:
            group_id = RELAY_GROUP_ID

    # 1) Лимит подряд входящих
    streak = await _repo.inc_streak(uid)
    if streak > USER_STREAK_LIMIT:
        try:
            await send_with_retry(
                msg.answer,
                f"Пожалуйста, дождись моего ответа 😘\nТвоё сообщение получено.\n— {MODEL_NAME}",
                logger=log,
            )
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
    log.info("IN: user_id=%s → group_id=%s text=%r", uid, group_id, content_text)
    try:
        # REGION AI: relay via helper
        await _send_record(msg, group_id, caption_header)
        # END REGION AI
    except Exception as e:
        log.exception("relay to group failed: %s", e)


# REGION AI: auto relay from group
async def _safe_edit_text(msg: Message, text: str, reply_markup: Any = None) -> None:
    current_text = msg.text or ""
    if current_text == text and msg.reply_markup == reply_markup:
        return
    await msg.edit_text(text, reply_markup=reply_markup)
# REGION AI: group replies
async def _copy_and_log(msg: Message, user_id: int) -> None:
    await msg.bot.copy_message(user_id, msg.chat.id, msg.message_id)
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


@router.message(
    F.chat.type.in_({"group", "supergroup"}),
    ~F.text.startswith("/"),
)
async def relay_from_group(msg: Message) -> None:
    group_id = msg.chat.id
    user_id: Optional[int] = None
    if get_user_by_group:
        try:
            user_id = await get_user_by_group(group_id)
        except Exception:
            user_id = None
    if user_id:
        text = msg.text or msg.caption or ""
        log.info("OUT: group_id=%s → user_id=%s text=%r", group_id, user_id, text)
        try:
            await _copy_and_log(msg, user_id)
        except Exception as e:
            log.error("relay_from_group: failed to deliver user_id=%s error=%s", user_id, e)
        finally:
            await _repo.reset_streak(user_id)
        return

    log.warning("relay_from_group: user not linked for group_id=%s", group_id)
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
        log.warning("relay_users: repository unavailable")
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
        await _copy_and_log(msg, user_id)
        if msg.text:
            await _safe_edit_text(msg, msg.text, reply_markup=None)
        log.info(
            "relay_from_group: delivered to user_id=%s type=%s",
            user_id,
            msg.content_type,
        )
    except Exception as e:
        log.error("relay_from_group: failed to deliver user_id=%s error=%s", user_id, e)
    finally:
        await _repo.reset_streak(user_id)
# END REGION AI
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
                await send_with_retry(
                    cmd.bot.send_message,
                    user_id,
                    text,
                    logger=log,
                )
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
                    await send_with_retry(
                        cmd.bot.send_message,
                        user_id,
                        args,
                        logger=log,
                    )
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

# REGION AI: link command
ADMIN_IDS: set[int] = set()


def _link_text(lang: str, key: str, user_id: int, group_id: int, chat_number: int) -> str:
    texts = {
        "ok": {
            "ru": f"✅ Пользователь {user_id} привязан к группе {group_id}, номер чата {chat_number}",
            "en": f"✅ User {user_id} linked to group {group_id}, chat number {chat_number}",
            "es": f"✅ Usuario {user_id} vinculado al grupo {group_id}, número de chat {chat_number}",
        },
        "bad": {
            "ru": "Использование: /link <user_id> <group_id>",
            "en": "Usage: /link <user_id> <group_id>",
            "es": "Uso: /link <user_id> <group_id>",
        },
        "forbidden": {
            "ru": "Команда доступна только администратору.",
            "en": "This command is only available to administrators.",
            "es": "Este comando solo está disponible para administradores.",
        },
    }
    return texts[key].get(lang, texts[key]["en"])


@router.message(Command("link"))
async def link_user_to_group(message: Message, command: CommandObject) -> None:
    lang = (message.from_user.language_code or "en")[:2]
    try:
        member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in {"administrator", "creator"}:
            raise ValueError
    except Exception:
        await message.reply(_link_text(lang, "forbidden", 0, 0, 0))
        return
    args = (command.args or "").split()
    if len(args) != 2 or not args[0].lstrip("-").isdigit() or not args[1].lstrip("-").isdigit():
        await message.reply(_link_text(lang, "bad", 0, 0, 0))
        return
    user_id, group_id = int(args[0]), int(args[1])
    if link_user_group:
        try:
            await link_user_group(user_id, group_id)
        except Exception:
            pass
    chat_number = get_chat_number(user_id) if get_chat_number else 0
    await message.reply(_link_text(lang, "ok", user_id, group_id, chat_number))
# END REGION AI

# fix: restrict /groupid command to admins
# REGION AI: groupid command
@router.message(Command("groupid"))
async def cmd_groupid(message: Message) -> None:
    lang = get_lang(message.from_user)
    if message.chat.type in {"group", "supergroup"}:
        if not message.from_user:
            await message.reply(tr(lang, "error_admin_only"))
            return
        try:
            member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        except Exception as e:  # pragma: no cover - network issues
            log.warning("cmd_groupid: get_chat_member failed: %s", e)
            await message.reply(tr(lang, "error_admin_only"))
            return
        if member.status not in {"administrator", "creator"}:
            await message.reply(tr(lang, "error_admin_only"))
            return
        await message.reply(f"Group ID: {message.chat.id}")
        log.info(
            "cmd_groupid: group_id=%s title=%s user_id=%s",
            message.chat.id,
            message.chat.title,
            message.from_user.id,
        )
        return
    if message.chat.type == "private" and message.from_user and message.from_user.id not in ADMIN_IDS:
        await message.reply(tr(lang, "error_group_only"))
        return
    await message.reply(tr(lang, "error_group_only"))
# END REGION AI
