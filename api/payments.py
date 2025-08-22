# api/payments.py
from fastapi import APIRouter, Request
from modules.payments import normalize_webhook
import logging

log = logging.getLogger("juicyfox.api.payments")
router = APIRouter()

@router.post("/payments/cryptobot")
async def cryptobot_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        # На случай если пришло не-JSON — просто завершим 200, но залогируем
        body = await request.body()
        log.error("cryptobot webhook non-JSON body: %r", body[:500])
        return {"ok": True}

    norm = normalize_webhook(payload)
    log.info("payment webhook received: %s", norm)

    # TODO:
    # - проверка подписи провайдера (если подключишь)
    # - обновление доступа пользователю по norm["meta"] (user_id, plan_code, bot_id)
    # - идемпотентность (не обрабатывать один invoice дважды)

    return {"ok": True}
