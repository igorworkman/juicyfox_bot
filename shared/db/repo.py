# shared/db/repo.py
from __future__ import annotations

import os
import time
import json
import logging
import aiosqlite
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

log = logging.getLogger("juicyfox.db")

DB_PATH = os.getenv("DB_PATH", "/app/data/juicyfox.sqlite")

# PRAGMA действуют на УРОВНЕ СОЕДИНЕНИЯ SQLite.
# Мы применяем их ровно один раз при открытии каждого соединения (см. _db()).
_PRAGMAS = [
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA foreign_keys=ON;",
    "PRAGMA temp_store=MEMORY;",
]

_SCHEMA = [
    # История сообщений
    """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        direction TEXT NOT NULL CHECK(direction IN ('in','out')),
        type TEXT NOT NULL,
        text TEXT,
        file_id TEXT,
        ts INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_messages_user_ts ON messages(user_id, ts);",

    # Счётчик «подряд входящих»
    """
    CREATE TABLE IF NOT EXISTS streaks (
        user_id INTEGER PRIMARY KEY,
        count INTEGER NOT NULL
    );
    """,

    # События платежей (нормализованные)
    """
    CREATE TABLE IF NOT EXISTS payment_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider TEXT,
        invoice_id TEXT,
        status TEXT,
        amount REAL,
        currency TEXT,
        meta TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_payment ON payment_events(provider, invoice_id, status);",

    # Логи выдачи доступов (invite-ссылки и срок)
    """
    CREATE TABLE IF NOT EXISTS access_grants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        plan_code TEXT NOT NULL,
        invite_link TEXT,
        until_ts INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_access_user ON access_grants(user_id);",

    # Незакрытые инвойсы (для повторной проверки при оплате/отмене)
    """
    CREATE TABLE IF NOT EXISTS pending_invoices (
        invoice_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        plan_code TEXT NOT NULL,
        currency TEXT NOT NULL,
        plan_callback TEXT,
        plan_name TEXT,
        price REAL,
        period INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
]


async def init_db() -> None:
    """Создаёт каталог и таблицы на диске, применяет PRAGMA для первичного соединения."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        for p in _PRAGMAS:
            await db.execute(p)
        for stmt in _SCHEMA:
            await db.execute(stmt)
        await db.commit()
    log.info("sqlite ready at %s", DB_PATH)


@asynccontextmanager
async def _db():
    """
    Асинхронный контекст подключения к БД:
    - открывает соединение
    - применяет PRAGMA ОДИН раз на это соединение
    - гарантированно закрывает соединение
    """
    # на всякий случай гарантируем каталог (если init_db забыли)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    try:
        for p in _PRAGMAS:
            await db.execute(p)
        yield db
    finally:
        await db.close()


# ============== История сообщений ==============

async def log_message(user_id: int, direction: str, content: Dict[str, Any]) -> None:
    """
    content: {'type': 'text'|'photo'|..., 'text': str|None, 'file_id': str|None, 'ts': int}
    """
    ts = int(content.get("ts") or time.time())
    typ = str(content.get("type") or "text")
    text = content.get("text")
    file_id = content.get("file_id")
    async with _db() as db:
        await db.execute(
            "INSERT INTO messages (user_id, direction, type, text, file_id, ts) VALUES (?,?,?,?,?,?)",
            (user_id, direction, typ, text, file_id, ts),
        )
        await db.commit()


async def get_history(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Возвращает ПОСЛЕДНИЕ N сообщений пользователя в хронологическом порядке (старые → новые).
    """
    async with _db() as db:
        cur = await db.execute(
            "SELECT direction, type, text, file_id, ts "
            "FROM messages WHERE user_id=? ORDER BY ts DESC LIMIT ?",
            (user_id, int(limit)),
        )
        rows = await cur.fetchall()

    rows.reverse()
    out: List[Dict[str, Any]] = []
    for direction, typ, text, file_id, ts in rows:
        out.append({
            "direction": direction,
            "type": typ,
            "text": text,
            "file_id": file_id,
            "ts": int(ts),
        })
    return out


# ============== Счётчики подряд входящих ==============

async def inc_streak(user_id: int) -> int:
    async with _db() as db:
        await db.execute(
            """
            INSERT INTO streaks(user_id, count) VALUES(?, 1)
            ON CONFLICT(user_id) DO UPDATE SET count = count + 1
            """,
            (user_id,),
        )
        await db.commit()
        cur = await db.execute("SELECT count FROM streaks WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return int(row[0]) if row else 1


async def reset_streak(user_id: int) -> None:
    async with _db() as db:
        await db.execute(
            "INSERT INTO streaks(user_id, count) VALUES(?, 0) ON CONFLICT(user_id) DO UPDATE SET count = 0",
            (user_id,),
        )
        await db.commit()


async def get_streak(user_id: int) -> int:
    async with _db() as db:
        cur = await db.execute("SELECT count FROM streaks WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return int(row[0]) if row else 0


# ============== (Опционально) Лог платежей/грантов ==============

async def save_pending_invoice(
    user_id: int,
    invoice_id: str,
    plan_code: str,
    currency: str,
    plan_callback: str,
    plan_name: str,
    price: float,
    period: int,
) -> None:
    async with _db() as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO pending_invoices(
                invoice_id, user_id, plan_code, currency,
                plan_callback, plan_name, price, period
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                invoice_id,
                user_id,
                plan_code,
                currency,
                plan_callback,
                plan_name,
                price,
                period,
            ),
        )
        await db.commit()


async def delete_pending_invoice(invoice_id: str) -> None:
    async with _db() as db:
        await db.execute("DELETE FROM pending_invoices WHERE invoice_id=?", (invoice_id,))
        await db.commit()


async def get_active_invoice(user_id: int) -> Optional[Dict[str, Any]]:
    async with _db() as db:
        cur = await db.execute(
            """
            SELECT invoice_id, plan_code, currency,
                   plan_callback, plan_name, price, period
            FROM pending_invoices
            WHERE user_id=?
            ORDER BY created_at DESC LIMIT 1
            """,
            (user_id,),
        )
        row = await cur.fetchone()
    if row:
        (
            invoice_id,
            plan_code,
            currency,
            plan_callback,
            plan_name,
            price,
            period,
        ) = row
        return {
            "invoice_id": invoice_id,
            "plan_code": plan_code,
            "currency": currency,
            "plan_callback": plan_callback,
            "plan_name": plan_name,
            "price": price,
            "period": period,
        }
    return None


async def delete_active_invoice(user_id: int) -> None:
    async with _db() as db:
        await db.execute("DELETE FROM pending_invoices WHERE user_id=?", (user_id,))
        await db.commit()

async def log_payment_event(event: Dict[str, Any]) -> None:
    """
    event: dict из normalize_webhook(...), поля: provider, invoice_id, status, amount, currency, meta
    """
    try:
        meta_json = json.dumps(event.get("meta") or {}, ensure_ascii=False)
        async with _db() as db:
            await db.execute(
                "INSERT OR IGNORE INTO payment_events(provider, invoice_id, status, amount, currency, meta) "
                "VALUES (?,?,?,?,?,?)",
                (
                    event.get("provider"),
                    event.get("invoice_id"),
                    event.get("status"),
                    float(event.get("amount") or 0),
                    event.get("currency") or "USD",
                    meta_json,
                ),
            )
            await db.commit()
    except Exception as e:
        # логируем, но не ломаем поток бота
        log.warning("log_payment_event failed: %s ; event=%r", e, event)


async def log_access_grant(user_id: int, plan_code: str, invite_link: Optional[str], until_ts: Optional[int]) -> None:
    async with _db() as db:
        await db.execute(
            "INSERT INTO access_grants(user_id, plan_code, invite_link, until_ts) VALUES (?,?,?,?)",
            (user_id, plan_code, invite_link, until_ts),
        )
        await db.commit()
