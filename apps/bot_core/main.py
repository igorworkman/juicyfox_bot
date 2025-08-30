# apps/bot_core/main.py
"""
Plan A — единый entrypoint:
- FastAPI принимает вебхуки и служебные эндпоинты
- aiogram Bot/Dispatcher живут здесь же
- Модули подключаются централизованно
- Webhook ставится на старте
"""
from dotenv import load_dotenv
load_dotenv()

import os
import logging
from contextlib import suppress

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from apps.bot_core.middleware import register_middlewares
from apps.bot_core.routers import register as register_routers
from api.main import logs_router
from shared.db.repo import init_db


# ---------- Обязательные ENV ----------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BOT_ID = os.getenv("BOT_ID", "sample")
BASE_URL = os.getenv("BASE_URL")         # например, https://your.domain
WEBHOOK_URL = os.getenv("WEBHOOK_URL")   # приоритет над BASE_URL

if not TELEGRAM_TOKEN or not BOT_ID:
    raise RuntimeError("Missing required env: TELEGRAM_TOKEN or BOT_ID")

# ---------- Логирование ----------
logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO"))
log = logging.getLogger("juicyfox.app")

# ---------- aiogram ----------
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
register_middlewares(dp)
register_routers(dp, cfg=None)

# ---------- FastAPI ----------
app = FastAPI(title="JuicyFox (Plan A)")
app.include_router(logs_router)

# Подключаем внешние API-роутеры (если есть)
with suppress(Exception):
    from api.webhook import router as webhook_router
    app.include_router(webhook_router)

with suppress(Exception):
    from api.payments import router as payments_router
    app.include_router(payments_router)

with suppress(Exception):
    from api.health import router as health_router
    app.include_router(health_router)

# ---------- Webhook (основной роут) ----------
@app.post("/bot/{bot_id}/webhook")
async def telegram_webhook(bot_id: str, request: Request):
    try:
        data = await request.json()
        log.info("📩 Incoming update for %s: %s", bot_id, data)  # 👈 логируем апдейт
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_webhook_update(bot, update)
        return {"ok": True}
    except Exception as e:
        log.exception("❌ Webhook error: %s", e)
        return {"ok": False}

# ---------- Webhook lifecycle ----------
@app.on_event("startup")
async def on_startup():
    await init_db()
    url = WEBHOOK_URL or (f"{BASE_URL}/bot/{BOT_ID}/webhook" if BASE_URL else None)
    if not url:
        log
