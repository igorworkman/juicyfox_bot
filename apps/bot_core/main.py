# apps/bot_core/main.py
"""
Plan A — единый entrypoint:
- FastAPI принимает вебхуки и служебные эндпоинты
- aiogram Bot/Dispatcher живут здесь же
- Модули подключаются централизованно
- Webhook ставится на старте
"""

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

# Сквозные middleware: контекст, rate-limit, перехват ошибок
register_middlewares(dp)

# Подключение модульных Router'ов (ui, posting, chat_relay, …)
# cfg можно передать позже, здесь None — все модули по умолчанию включены
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

# Простая /healthz, если отдельного модуля нет
if not any(getattr(r, "path", None) == "/healthz" for r in app.router.routes):
    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "bot_id": BOT_ID}

# Совместимость со старым URL (/webhook/bot/{bot_id}/webhook)
@app.post("/webhook/bot/{bot_id}/webhook")
async def telegram_webhook_compat(bot_id: str, request: Request):
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_webhook_update(bot, update)
        return {"ok": True}
    except Exception as e:
        log.exception("webhook compat error: %s", e)
        return {"ok": False}

# ---------- Webhook lifecycle ----------
@app.on_event("startup")
async def on_startup():
    # 0) Инициализируем БД (персистентный volume /app/data)
    with suppress(Exception):
        from shared.db.repo import init_db
        await init_db()

    # 1) Ставим webhook (если указан URL)
    url = WEBHOOK_URL or (f"{BASE_URL}/bot/{BOT_ID}/webhook" if BASE_URL else None)
    if not url:
        log.warning("BASE_URL/WEBHOOK_URL is not set — webhook will not be installed.")
        return
    try:
        await bot.set_webhook(url, drop_pending_updates=True)
        log.info("Webhook set for %s → %s", BOT_ID, url)
    except Exception as e:
        log.exception("Failed to set webhook: %s", e)

@app.on_event("shutdown")
async def on_shutdown():
    with suppress(Exception):
        await bot.delete_webhook(drop_pending_updates=False)
        log.info("Webhook deleted for %s", BOT_ID)
