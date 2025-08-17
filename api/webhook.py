from fastapi import APIRouter, Request
from aiogram.types import Update

router = APIRouter()


@router.post("/bot/{bot_id}/webhook")
async def telegram_webhook(bot_id: str, request: Request):
    from apps.bot_core.main import bot, dp

    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}
