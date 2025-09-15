# modules/access/__init__.py
from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from aiogram import Bot

log = logging.getLogger("juicyfox.access")

# Карта планов → переменная окружения с chat_id и срок действия (дней)
# plan to chat_id mapping
PLAN_MAP: Dict[str, Dict[str, Any]] = {
    "vip_30d": {"env": "VIP_CHANNEL_ID", "days": 30}, "chat_10d": {"env": "CHAT_GROUP_ID", "days": 10},
    "chat_20d": {"env": "CHAT_GROUP_ID", "days": 20}, "chat_30d": {"env": "CHAT_GROUP_ID", "days": 30}
}

class AccessError(Exception):
    pass


def _chat_id_for_plan(plan_code: str) -> int:
    cfg = PLAN_MAP.get(plan_code)
    if not cfg:
        raise AccessError(f"Unknown plan_code={plan_code}")
    env = cfg["env"]
    raw = os.getenv(env)
    if not raw:
        raise AccessError(f"{env} is not set for plan_code={plan_code}")
    try:
        return int(raw)
    except Exception:
        # поддержим форматы -100... и @username на будущее
        if raw.startswith("@"):
            raise AccessError("Username-based chat ids are not supported here, provide numeric id")
        raise


async def grant(user_id: int, plan_code: str, *, bot: Optional[Bot] = None) -> Dict[str, Any]:
    """
    Выдать доступ пользователю:
      - создаём invite-link с ограничением по времени и 1 использованием
      - возвращаем {'invite_link': 'https://t.me/+...', 'until': <datetime>}
      - (опц.) шлём ссылку пользователю, если bot передан
    """
    chat_id = _chat_id_for_plan(plan_code)
    days = int(PLAN_MAP[plan_code]["days"])
    until = datetime.now(timezone.utc) + timedelta(days=days)

    if bot is None:
        try:
            # пытаемся взять глобальный bot из ядра
            from apps.bot_core.main import bot as core_bot  # type: ignore
        except Exception:
            core_bot = None
        bot = core_bot

    if bot is None:
        raise AccessError("Bot instance is not available")

    # создаём персональную ссылку
    link = await bot.create_chat_invite_link(
        chat_id=chat_id,
        name=f"{plan_code}:{user_id}",
        expire_date=until,
        member_limit=1,
        creates_join_request=False,
    )

    result = {"invite_link": link.invite_link, "until": until.isoformat()}
    log.info("access.grant: plan=%s user=%s chat=%s until=%s",
             plan_code, user_id, chat_id, result["until"])

    # Мягко отправим пользователю ссылку
    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"✅ Доступ по плану **{plan_code}**. Срок до {until.date()}\nСсылка: {link.invite_link}",
            parse_mode="Markdown",
        )
    except Exception as e:
        log.warning("cannot DM user %s invite link (maybe user never started bot): %s", user_id, e)

    return result


async def process_payment_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Обработать нормализованный вебхук платежа (см. modules.payments.service.normalize_webhook):
    ожидает поля: provider, status, meta{user_id, plan_code, bot_id}
    Выполняет grant() при status == 'paid'.
    Возвращает {'handled': bool, 'duplicate': bool, ...}
    """
    status = (event.get("status") or "").lower()
    duplicate = bool(event.get("duplicate"))
    meta = event.get("meta") or {}
    user_id = int(meta.get("user_id") or 0)
    plan_code = str(meta.get("plan_code") or "")

    if not user_id or not plan_code:
        return {"handled": False, "reason": "missing meta", "duplicate": duplicate}

    if status != "paid":
        return {"handled": False, "reason": f"status={status}", "duplicate": duplicate}

    try:
        granted = await grant(user_id=user_id, plan_code=plan_code)
        return {"handled": True, "duplicate": duplicate, **granted}
    except Exception as e:
        log.exception("process_payment_event failed: %s", e)
        return {"handled": False, "duplicate": duplicate, "error": str(e)}
