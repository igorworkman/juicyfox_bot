# apps/bot_core/main.py
"""
apps/bot_core/main.py — План A entrypoint

Единая точка входа FastAPI + инициализация aiogram (Bot/Dispatcher).
Поддерживает один webhook на инстанс бота и модульную маршрутизацию.
"""

import os
import logging
from contextlib import suppress

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher

# -------------------------
# ENV / базовая конфигурация
# -------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # обязателен
BOT_ID = os.getenv("BOT_ID", "sample")        # идентификатор инстанса
BASE_URL = os.getenv("BASE_URL")              # базовый публичный URL (для формирования webhook)
WEBHOOK_URL = os.getenv("WEBHOOK_URL")        # если задан, используем его как есть

# Логирование
logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO"))
log = logging.getLogger("juicyfox.app")

# -------------------------
# aiogram объекты (глобально, чтобы их мог импортировать api/webhook)
# -------------------------
bot = Bot(token=TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
dp = Dispatcher()

# Регистрируем модульные роутеры aiogram
def register_aiogram_routers() -> None:
    # UI / меню / донаты / VIP / чат — обязательный модуль
    with suppress(Exception):
        from modules.ui_membership.handlers import router as ui_router
        dp.include_router(ui_router)

    # Постинг — опционально (по наличию)
    with suppress(Exception):
        from modules.posting.handlers import router as posting_router
        dp.include_router(posting_router)

    # Чат-релей — опционально
    with suppress(Exception):
        from modules.chat_relay.handlers import router as chat_router
        dp.include_router(chat_router)

register_aiogram_routers()

# -------------------------
# FastAPI приложение
# -------------------------
app = FastAPI(title="JuicyFox (Plan A)")

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

# Если отдельного health-роутера нет — добавим простейший эндпоинт здесь
if not any(getattr(r, "path", None) == "/healthz" for r in app.router.routes):
    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "bot_id": BOT_ID}

# Совместимость со старым путём /webhook/bot/{bot_id}/webhook
@app.post("/webhook/bot/{bot_id}/webhook")
async def telegram_webhook_compat(bot_id: str, request: Request):
    """
    Совместимый маршрут со старой схемой URL.
    Логика идентична /bot/{bot_id}/webhook из api.webhook.
    """
    if bot is None:
        return {"ok": False, "error": "TELEGRAM_TOKEN is not set"}
    try:
        from aiogram.types import Update
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_webhook_update(bot, update)
        return {"ok": True}
    except Exception as e:
        log.exception("webhook compat error: %s", e)
        return {"ok": False}

# -------------------------
# Webhook lifecycle
# -------------------------
@app.on_event("startup")
async def on_startup():
    if bot is None:
        log.warning("TELEGRAM_TOKEN is not provided – bot is not initialized.")
        return
    # Формируем URL webhook
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
    if bot is None:
        return
    with suppress(Exception):
        await bot.delete_webhook(drop_pending_updates=False)
        log.info("Webhook deleted for %s", BOT_ID)
