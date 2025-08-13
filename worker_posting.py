import os
linaus-codex/instantiate-bot-without-webhook-or-polling
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

import asyncio
import logging
import time
from typing import Dict, Any

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
import aiosqlite

try:
    import redis.asyncio as aioredis
except Exception:  # pragma: no cover - redis is optional
    aioredis = None

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_GROUP_ID = int(os.getenv("CHAT_GROUP_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "/app/data/juicyfox.db")
REDIS_URL = os.getenv("REDIS_URL")
STREAM_NAME = os.getenv("STREAM_NAME", "events")
GROUP_NAME = os.getenv("REDIS_GROUP", "posting")

log = logging.getLogger(__name__)


async def _send_event(bot: Bot, event: Dict[str, Any]) -> None:
    """Send an event to the posting group."""
    src_chat_id = event.get("src_chat_id")
    msg_id = event.get("msg_id")
    text = event.get("text")
    if msg_id and src_chat_id:
        await bot.copy_message(CHAT_GROUP_ID, int(src_chat_id), int(msg_id))
    else:
        await bot.send_message(CHAT_GROUP_ID, text or "")


async def process_db_events(bot: Bot) -> None:
    """Read events from SQLite table and post them to the group."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                src_chat_id INTEGER,
                msg_id INTEGER,
                text TEXT,
                run_at INTEGER,
                status TEXT DEFAULT 'pending',
                error TEXT
            )
            """
        )
        await db.commit()

        while True:
            now = int(time.time())
            async with db.execute(
                """
                SELECT * FROM events
                WHERE status = 'pending' AND run_at <= ?
                ORDER BY run_at ASC
                LIMIT 1
                """,
                (now,),
            ) as cursor:
                event = await cursor.fetchone()

            if not event:
                await asyncio.sleep(1)
                continue

            await db.execute(
                "UPDATE events SET status = 'processing' WHERE id = ?", (event["id"],)
            )
            await db.commit()

            try:
                await _send_event(bot, event)
                await db.execute(
                    "UPDATE events SET status = 'done' WHERE id = ?", (event["id"],)
                )
            except Exception as e:  # pragma: no cover - network errors
                log.exception("Failed to post event %s", event["id"])
                await db.execute(
                    "UPDATE events SET status = 'failed', error = ? WHERE id = ?",
                    (str(e), event["id"]),
                )
            await db.commit()


async def process_redis_events(bot: Bot) -> None:
    """Consume events from Redis Stream and post them."""
    if aioredis is None:
        raise RuntimeError("redis package is required for Redis mode")

    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    consumer = os.getenv("WORKER_NAME", "worker")

    try:
        await r.xgroup_create(STREAM_NAME, GROUP_NAME, id="0", mkstream=True)
    except Exception:
        pass  # group already exists

    while True:
        messages = await r.xreadgroup(
            GROUP_NAME, consumer, {STREAM_NAME: ">"}, count=1, block=5000
        )
        if not messages:
            continue
        for _, events in messages:
            for msg_id, data in events:
                try:
                    await _send_event(bot, data)
                except Exception as e:  # pragma: no cover - network errors
                    log.exception("Failed to post event %s", msg_id)
                finally:
                    await r.xack(STREAM_NAME, GROUP_NAME, msg_id)


async def main() -> None:
    if not TELEGRAM_TOKEN or not CHAT_GROUP_ID:
        raise RuntimeError("TELEGRAM_TOKEN and CHAT_GROUP_ID must be set")

    session = AiohttpSession()
    bot = Bot(token=TELEGRAM_TOKEN, session=session, parse_mode="HTML")
    try:
        if REDIS_URL:
            await process_redis_events(bot)
        else:
            await process_db_events(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
 main
