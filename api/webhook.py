import logging
import os

from fastapi import APIRouter, Request, Response, status
from aiogram.types import Update

from shared.db import repo as db_repo
from shared.utils import idempotency

router = APIRouter()
log = logging.getLogger("juicyfox.api.webhook")

BOT_ID = os.getenv("BOT_ID", "telegram")
IDEMPOTENCY_TTL_SECONDS = 300

@router.post("/webhook")
async def telegram_webhook(request: Request) -> Response:
    """
    Принимаем апдейты от Telegram на /webhook.
    - Всегда стараемся вернуть 200/204, чтобы Telegram не копил ошибки.
    - Любые ошибки парсинга логируем, но не роняем обработчик.
    """
    try:
        # Telegram шлёт JSON; если тело пустое/битое — вернём 204
        data = await request.json()
        if not data or not isinstance(data, dict):
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        # Ленивый импорт, чтобы не ловить циклические зависимости
        from apps.bot_core.main import bot, dp

        # Валидируем апдейт и проверяем идемпотентность перед передачей
        update = Update.model_validate(data, context={"bot": bot})
        idem_key = idempotency.telegram_update_key(BOT_ID, update)
        is_new = await db_repo.claim_idempotency_key(idem_key, ttl_seconds=IDEMPOTENCY_TTL_SECONDS)
        if not is_new:
            log.debug("duplicate telegram update skipped: %s", idem_key)
            return Response(status_code=status.HTTP_200_OK)

        # Прокармливаем апдейт диспетчеру только один раз
        await dp.feed_webhook_update(bot, update)

        # Всё ок — можно вернуть 200
        return Response(status_code=status.HTTP_200_OK)

    except Exception as e:
        # Не роняем 500 — Telegram будет ретраить и копить last_error_message.
        # Лучше проглотить и вернуть 200/204, а в своих логах посмотреть причину.
        try:
            # Минимальная попытка журналирования в stdout/stderr
            log.exception("webhook error: %s", e)
        except Exception:
            pass
        return Response(status_code=status.HTTP_200_OK)
