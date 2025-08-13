import os
import logging
from typing import Optional
from aiogram import Bot

log = logging.getLogger(__name__)

# Instantiate the Bot once per worker without webhook or polling
BOT_TOKEN = os.getenv("BOT_TOKEN")
_bot: Optional[Bot] = None

def get_bot() -> Bot:
    """Lazily create a Bot instance for sending messages."""
    global _bot
    if _bot is None:
        if not BOT_TOKEN:
            raise RuntimeError("BOT_TOKEN is not set")
        _bot = Bot(BOT_TOKEN)
    return _bot

async def send_text(chat_id: int, text: str) -> None:
    """Send a text message."""
    bot = get_bot()
    await bot.send_message(chat_id, text)

async def copy(from_chat_id: int, message_id: int, to_chat_id: int) -> None:
    """Copy a message from one chat to another."""
    bot = get_bot()
    await bot.copy_message(to_chat_id, from_chat_id, message_id)

async def close_bot() -> None:
    """Close the Bot's HTTP session."""
    bot = get_bot()
    await bot.session.close()
