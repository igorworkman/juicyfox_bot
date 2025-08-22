from fastapi import APIRouter, Request
from modules.payments import normalize_webhook
import logging

log = logging.getLogger("juicyfox.api.payments")

router = APIRouter()


@router.post("/payments/cryptobot")
async def cryptobot_webhook(request: Request):
    payload = await request.json()
    norm = normalize_webhook(payload)
    log.info("payment webhook received: %s", norm)
    # TODO: здесь можно будет обновить доступ пользователя по norm["meta"]
    return {"ok": True}
