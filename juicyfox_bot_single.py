# JuicyFox Bot — single‑file (aiogram 3.20) + 30‑day access
# ---------------------------------------------------------
# • Club / VIP / Chat  → 8 валют → счёт → доступ ровно 30 суток
# • Donate             → валюта → сумма (USD) → счёт
# • Relay              → приват ↔ группа (CHAT_GROUP_ID)
# • RU/EN UI           → auto by language_code

#  !! PING COMMIT test !!! - noreal changes, to trigger autobuild on Northfhank
# ** MARKER !!!

# *** Code below not changed ***
import os, logging, asyncio, httpx, time, aiosqlite
from typing import Dict, Any, Optional, Tuple
from aiogram import Bot, Dispatcher, Router, F

from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSLContext
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ---------------- Config ----------------------------
TELEGRAM_TOKEN   = os.getenv('TELEGRAM_TOKEN')
CRYPTOBOT_TOKEN = os.getenv('CRYPTOBOT_TOKEN') or os.getenv('CRYPTO_BOT_TOKEN')
CHAT_GROUP_ID   = int(os.getenv('CHAT_GROUP_ID', '-1002813332213'))
LIVE_CHANNEL_URL= os.getenv('LIVE_CHANNEL_URL', 'https://t.me/JuisyFoxOfficialLife')
API_BASE        = 'https://pay.crypt.bot/api'
VIP_CHANNEL_ID  = int(os.getenv('VIP_CHANNEL_ID', '-1001234567890'))  # приватный VIP‑канал
DB_PATH         = 'juicyfox.db'

if not TELEGRAM_TOKEN or not CRYPTOBOT_TOKEN:
    raise RuntimeError('Set TELEGRAM_TOKEN and CRYPTOBOT_TOKEN env vars')

bot = Bot(TELEGRAM_TOKEN, parse_mode='HTML')
dp  = Dispatcher(storage=MemoryStorage())

# ... rest was not handled changed

if __name__ == '__main__':
    asyncio.run(main())
