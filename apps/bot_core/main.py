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

# ---------- Роуты ----------
@app.post("/bot/{bot_id}/webhook")
async def telegram_webhook(bot_id: str,
