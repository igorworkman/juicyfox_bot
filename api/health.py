# api/health.py
from fastapi import APIRouter
import os
from contextlib import suppress

# Берём общие объекты из ядра (если доступны)
with suppress(Exception):
    from apps.bot_core.main import bot, dp, BOT_ID  # type: ignore
else:
    bot = None
    dp = None
    BOT_ID = os.getenv("BOT_ID", "unknown")

router = APIRouter()

@router.get("/healthz")
async def healthz():
    return {"status": "ok", "bot_id": BOT_ID, "telegram_initialized": bool(bot)}

@router.get("/readyz")
async def readyz():
    # Простой критерий "готовности": инициализированы bot и dp
    return {"ready": bool(bot and dp), "bot_id": BOT_ID}

@router.get("/livez")
async def livez():
    # Лайвнесс обычно просто "живое приложение"
    return {"alive": True}
