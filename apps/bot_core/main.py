import os
import asyncio
import logging

from aiogram import Bot, Dispatcher
from fastapi import FastAPI

from modules.ui_membership.handlers import router as router_ui
from router_pay import router as router_pay
from router_posting import router as router_posting
from router_relay import router as router_relay

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BASE_URL = os.getenv("BASE_URL")
BOT_ID = os.getenv("BOT_ID")

app = FastAPI()
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

dp.include_router(router_ui)
dp.include_router(router_pay)
dp.include_router(router_posting)
dp.include_router(router_relay)


@app.on_event("startup")
async def on_startup():
    webhook_url = f"{BASE_URL}/bot/{BOT_ID}/webhook"
    info = await bot.get_webhook_info()
    if info.url != webhook_url:
        await bot.set_webhook(webhook_url, drop_pending_updates=True)
    logging.info(f"Webhook set to {webhook_url}")

from api.webhook import router as webhook_router

app.include_router(webhook_router)
