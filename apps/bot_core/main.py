import os
import asyncio
import logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from fastapi import FastAPI

from modules.ui_membership.handlers import router as router_ui
from router_pay import router as router_pay
from router_posting import router as router_posting
from router_relay import router as router_relay

# Load environment variables from a local .env file if present
load_dotenv()

# Required environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BASE_URL = os.getenv("BASE_URL")
BOT_ID = os.getenv("BOT_ID")

if not TELEGRAM_TOKEN or not BASE_URL or not BOT_ID:
    raise RuntimeError(
        "❌ Missing required environment variables: TELEGRAM_TOKEN, BASE_URL or BOT_ID"
    )

# Optional environment variables
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")
VIP_CHANNEL_ID = os.getenv("VIP_CHANNEL_ID")
LIFE_CHANNEL_ID = os.getenv("LIFE_CHANNEL_ID")
LUXURY_CHANNEL_ID = os.getenv("LUXURY_CHANNEL_ID")
POST_PLAN_GROUP_ID = os.getenv("POST_PLAN_GROUP_ID")
CHAT_GROUP_ID = os.getenv("CHAT_GROUP_ID")
HISTORY_GROUP_ID = os.getenv("HISTORY_GROUP_ID")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
VIP_URL = os.getenv("VIP_URL")
LIFE_URL = os.getenv("LIFE_URL")
NORTHFLANK_API_TOKEN = os.getenv("NORTHFLANK_API_TOKEN")
NORTHFLANK_PROJECT_ID = os.getenv("NORTHFLANK_PROJECT_ID")
NORTHFLANK_SERVICE_ID = os.getenv("NORTHFLANK_SERVICE_ID")

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
