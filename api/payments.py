# api/payments.py
from fastapi import APIRouter, Request
from modules.payments import normalize_webhook
from modules.access import process_payment_event
import logging

log = logging.getLogger("juicyfox.api.payments")
router = APIRouter()

@router.post("/payments/cryptobot")
async def cryptobot_webhook(request: Request):
    # 1) безопасно читаем JSON
    try:
        payload = await request.json()
    except Exception:
        body = await request.body()
        log.error("cryptobot webhook non-JSON body: %r", body[:500])
        return {"ok": True, "handled": False, "reason": "non-json"}

    # 2) нормализуем до единого формата
    norm = normalize_webhook(payload)
    log.info("payment webhook received: %s", norm)

    # 3) обрабатываем событие (выдача инвайта при status=='paid')
    result = await process_payment_event(norm)
    log.info("payment processed: %s", result)

    # 4) всегда 200 OK для провайдера, подробности — в теле ответа/логах
    return {"ok": True, **result}
