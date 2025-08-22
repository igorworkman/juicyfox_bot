# modules/posting/worker.py
from __future__ import annotations

import os
import asyncio
import time
import logging
from typing import Any, Dict, List, Tuple

import aiosqlite
from aiogram import Bot

log = logging.getLogger("juicyfox.posting.worker")

DB_PATH = os.getenv("DB_PATH", "/app/data/juicyfox.sqlite")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
POLL_INTERVAL_SEC = int(os.getenv("POST_WORKER_INTERVAL", "5"))
BATCH_LIMIT = int(os.getenv("POST_WORKER_BATCH", "20"))

_PRAGMAS = [
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA foreign_keys=ON;",
    "PRAGMA temp_store=MEMORY;",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS post_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    text TEXT,
    file_id TEXT,
    run_at INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending|sent|failed
    retries INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_post_queue_run ON post_queue(status, run_at);
"""

async def _ensure_schema():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        for p in _PRAGMAS:
            await db.execute(p)
        for stmt in _SCHEMA.split(";"):
            st = stmt.strip()
            if st:
                await db.execute(st)
        await db.commit()

async def _fetch_due(limit: int) -> List[Dict[str, Any]]:
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        for p in _PRAGMAS:
            await db.execute(p)
        cur = await db.execute(
            "SELECT id, chat_id, type, text, file_id "
            "FROM post_queue WHERE status='pending' AND run_at<=? "
            "ORDER BY run_at ASC LIMIT ?",
            (now, int(limit)),
        )
        rows = await cur.fetchall()
    jobs: List[Dict[str, Any]] = []
    for row in rows:
        jid, chat_id, typ, text, file_id = row
        jobs.append({"id": int(jid), "chat_id": int(chat_id), "type": typ, "text": text, "file_id": file_id})
    return jobs

async def _mark_sent(job_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        for p in _PRAGMAS:
            await db.execute(p)
        await db.execute("UPDATE post_queue SET status='sent' WHERE id=?", (job_id,))
        await db.commit()

async def _mark_failed(job_id: int, err: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        for p in _PRAGMAS:
            await db.execute(p)
        # простейший backoff: 30 * 2^retries, максимум 15 минут
        cur = await db.execute("SELECT retries FROM post_queue WHERE id=?", (job_id,))
        row = await cur.fetchone()
        retries = int(row[0]) if row else 0
        delay = min(900, 30 * (2 ** retries))
        next_ts = int(time.time()) + delay
        await db.execute(
            "UPDATE post_queue SET retries=retries+1, error=?, run_at=?, status='pending' WHERE id=?",
            (err[:200], next_ts, job_id),
        )
        await db.commit()

async def _send(bot: Bot, job: Dict[str, Any]) -> None:
    typ = job["type"]
    chat_id = job["chat_id"]
    text = job.get("text")
    file_id = job.get("file_id")

    if typ == "text":
        await bot.send_message(chat_id, text or "")
    elif typ == "photo":
        await bot.send_photo(chat_id, file_id, caption=text)
    elif typ == "video":
        await bot.send_video(chat_id, file_id, caption=text)
    elif typ == "document":
        await bot.send_document(chat_id, file_id, caption=text)
    elif typ == "animation":
        await bot.send_animation(chat_id, file_id, caption=text)
    else:
        raise RuntimeError(f"unsupported type: {typ}")

async def main() -> None:
    if not TELEGRAM_TOKEN:
        raise RuntimeError("POSTING WORKER: TELEGRAM_TOKEN is required")

    await _ensure_schema()
    bot = Bot(token=TELEGRAM_TOKEN)

    log.info("posting worker started; db=%s interval=%ss batch=%s", DB_PATH, POLL_INTERVAL_SEC, BATCH_LIMIT)

    while True:
        try:
            jobs = await _fetch_due(BATCH_LIMIT)
            if not jobs:
                await asyncio.sleep(POLL_INTERVAL_SEC)
                continue

            for job in jobs:
                jid = job["id"]
                try:
                    await _send(bot, job)
                    await _mark_sent(jid)
                    log.info("post sent id=%s → chat_id=%s", jid, job["chat_id"])
                except Exception as e:
                    await _mark_failed(jid, str(e))
                    log.warning("post failed id=%s: %s", jid, e)

        except Exception as loop_err:
            log.exception("worker loop error: %s", loop_err)
            await asyncio.sleep(POLL_INTERVAL_SEC)
