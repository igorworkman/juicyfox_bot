# api/webhook.py
from fastapi import APIRouter, Request, HTTPException
from aiogram.types import Update
import os

router = APIRouter()

# Общая функция обработки: парсим апдейт и скармливаем диспетчеру
async def _process_update(request: Request):
    from apps.bot_core.main import bot, dp  # импортируем актуальные инстансы
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_webhook_update(bot, update)
    return {"ok": True}

# 1) Новый путь — на него сейчас выставлен вебхук
@router.post("/webhook")
async def webhook_plain(request: Request):
    return await _process_update(request)

# 2) Совместимость со старым путём
@router.post("/bot/{bot_id}/webhook")
async def webhook_with_bot_id(bot_id: str, request: Request):
    # (опциональная защита) можно проверять соответствие BOT_ID из окружения
    env_bot_id = os.getenv("BOT_ID")
    if env_bot_id and env_bot_id != bot_id:
        # если хотите просто игнорировать, верните 200; если хотите жёстко — 403
        raise HTTPException(status_code=403, detail="BOT_ID mismatch")
    return await _process_update(request)
