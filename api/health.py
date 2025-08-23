from fastapi import APIRouter
import os

try:
    from apps.bot_core.main import bot, dp, BOT_ID  # type: ignore
except Exception:
    bot = None
    dp = None
    BOT_ID = os.getenv("BOT_ID", "unknown")

router = APIRouter()

@router.get("/healthz")
async def healthz():
    return {"status": "ok", "bot_id": BOT_ID, "telegram_initialized": bool(bot)}

@router.get("/readyz")
async def readyz():
    return {"ready": bool(bot and dp), "bot_id": BOT_ID}

@router.get("/livez")
async def livez():
    return {"alive": True}
