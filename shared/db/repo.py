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

# Флаг, чтобы сообщение о миграции схемы выводилось только один раз
_SCHEMA_LOGGED = False

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
    # REGION AI: relay_users table
    """
    CREATE TABLE IF NOT EXISTS relay_users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    # END REGION AI
    # feat: store user to group links
    # REGION AI: users table
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        group_id INTEGER NOT NULL,
        chat_number INTEGER,
        status TEXT NOT NULL DEFAULT 'active',
        linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    # END REGION AI
    # Очередь рассылок
    """
    CREATE TABLE IF NOT EXISTS mailings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT,
        type TEXT,
        file_id TEXT,
        text TEXT,
        run_at INTEGER,
        status TEXT,
        error TEXT,
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
        cur = await db.execute("PRAGMA table_info(pending_invoices)")
        cols = {r[1] for r in await cur.fetchall()}
        if "plan_callback" not in cols:
            await db.execute("ALTER TABLE pending_invoices ADD COLUMN plan_callback TEXT")
        if "plan_name" not in cols:
            await db.execute("ALTER TABLE pending_invoices ADD COLUMN plan_name TEXT")
        if "price" not in cols:
            await db.execute("ALTER TABLE pending_invoices ADD COLUMN price REAL")
        if "period" not in cols:
            await db.execute("ALTER TABLE pending_invoices ADD COLUMN period INTEGER")
        cur = await db.execute("PRAGMA table_info(users)")
        cols = {r[1] for r in await cur.fetchall()}
        if "chat_number" not in cols:
            await db.execute("ALTER TABLE users ADD COLUMN chat_number INTEGER")
        await db.commit()

    global _SCHEMA_LOGGED
    if not _SCHEMA_LOGGED:
        log.info("DB schema migrated: pending_invoices ready")
        _SCHEMA_LOGGED = True

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
    sql = (
        """
        INSERT OR REPLACE INTO pending_invoices(
            invoice_id, user_id, plan_code, currency,
            plan_callback, plan_name, price, period
        ) VALUES (?,?,?,?,?,?,?,?)
        """
    )
    params = (
        invoice_id,
        user_id,
        plan_code,
        currency,
        plan_callback,
        plan_name,
        price,
        period,
    )
    try:
        log.info(
            "Executing SQL: %s ; invoice_id=%s plan_code=%s plan_callback=%s user_id=%s",
            sql.strip(),
            invoice_id,
            plan_code,
            plan_callback,
            user_id,
        )
        async with _db() as db:
            await db.execute(sql, params)
            await db.commit()
        log.info(
            "save_pending_invoice success: invoice_id=%s plan_code=%s user_id=%s",
            invoice_id,
            plan_code,
            user_id,
        )
    except Exception:
        log.exception(
            "save_pending_invoice failed: invoice_id=%s plan_code=%s plan_callback=%s user_id=%s sql=%s",
            invoice_id,
            plan_code,
            plan_callback,
            user_id,
            sql.strip(),
        )


async def delete_pending_invoice(invoice_id: str) -> int:
    sql = "DELETE FROM pending_invoices WHERE invoice_id=?"
    try:
        async with _db() as db:
            cur = await db.execute(
                "SELECT user_id, plan_code, plan_callback FROM pending_invoices WHERE invoice_id=?",
                (invoice_id,),
            )
            row = await cur.fetchone()
            user_id = row[0] if row else None
            plan_code = row[1] if row else None
            plan_callback = row[2] if row else None
            log.info(
                "Executing SQL: %s ; invoice_id=%s user_id=%s plan_code=%s plan_callback=%s",
                sql,
                invoice_id,
                user_id,
                plan_code,
                plan_callback,
            )
            cur = await db.execute(sql, (invoice_id,))
            await db.commit()
            deleted = cur.rowcount
        if deleted:
            log.info("delete_pending_invoice success: invoice_id=%s rows=%s", invoice_id, deleted)
        else:
            log.warning("delete_pending_invoice no rows deleted: invoice_id=%s", invoice_id)
        return int(deleted)
    except Exception:
        log.exception("delete_pending_invoice failed: invoice_id=%s sql=%s", invoice_id, sql)
        return 0


async def get_active_invoice(user_id: int) -> Optional[Dict[str, Any]]:
    sql = (
        """
        SELECT invoice_id, plan_code, currency,
               plan_callback, plan_name, price, period
        FROM pending_invoices
        WHERE user_id=?
        ORDER BY created_at DESC LIMIT 1
        """
    )
    try:
        log.info(
            "Executing SQL: %s ; invoice_id=%s plan_code=%s plan_callback=%s user_id=%s",
            sql.strip(),
            None,
            None,
            None,
            user_id,
        )
        async with _db() as db:
            cur = await db.execute(sql, (user_id,))
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
            log.info(
                "get_active_invoice success: invoice_id=%s plan_code=%s plan_callback=%s user_id=%s",
                invoice_id,
                plan_code,
                plan_callback,
                user_id,
            )
            return {
                "invoice_id": invoice_id,
                "plan_code": plan_code,
                "currency": currency,
                "plan_callback": plan_callback,
                "plan_name": plan_name,
                "price": price,
                "period": period,
            }
        log.info(
            "get_active_invoice success: invoice_id=%s plan_code=%s plan_callback=%s user_id=%s",
            None,
            None,
            None,
            user_id,
        )
        return None
    except Exception:
        log.exception(
            "get_active_invoice failed: invoice_id=%s plan_code=%s plan_callback=%s user_id=%s sql=%s",
            None,
            None,
            None,
            user_id,
            sql.strip(),
        )
        return None


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


# REGION AI: user profile
def get_user_profile(user_id: int) -> tuple[float, Optional[int]]:
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        total = cur.execute(
            "SELECT COALESCE(SUM(amount),0) FROM payment_events "
            "WHERE status='paid' AND json_extract(meta,'$.user_id')=?",
            (user_id,),
        ).fetchone()[0] or 0.0
        row = cur.execute(
            "SELECT until_ts FROM access_grants WHERE user_id=? "
            "AND until_ts IS NOT NULL ORDER BY until_ts DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        conn.close()
        return float(total), (int(row[0]) if row and row[0] else None)
    except Exception:  # pragma: no cover
        return 0.0, None
# END REGION AI

# REGION AI: relay_users helpers
async def upsert_relay_user(user_id: int, username: Optional[str], full_name: Optional[str]) -> None:
    async with _db() as db:
        await db.execute(
            "INSERT INTO relay_users(user_id, username, full_name, last_seen) VALUES(?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name, last_seen=CURRENT_TIMESTAMP",
            (user_id, username, full_name),
        )
        await db.commit()


async def get_relay_user(user_id: int) -> Optional[Dict[str, Any]]:
    async with _db() as db:
        row = await (
            await db.execute(
                "SELECT user_id, username, full_name, last_seen FROM relay_users WHERE user_id=?",
                (user_id,),
            )
        ).fetchone()
    return {"user_id": row[0], "username": row[1], "full_name": row[2], "last_seen": row[3]} if row else None


async def get_all_relay_users() -> List[Dict[str, Any]]:
    async with _db() as db:
        rows = await (await db.execute("SELECT user_id, username, full_name, last_seen FROM relay_users")).fetchall()
    return [{"user_id": r[0], "username": r[1], "full_name": r[2], "last_seen": r[3]} for r in rows]
# END REGION AI

# REGION AI: user helpers
def get_chat_number(user_id: int) -> Optional[int]:
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT chat_number FROM users WHERE user_id=?", (user_id,)).fetchone()
        conn.close()
        return int(row[0]) if row and row[0] is not None else None
    except Exception:  # pragma: no cover
        return None


async def get_user_status(user_id: int) -> Optional[str]:
    async with _db() as db:
        row = await (await db.execute("SELECT status FROM users WHERE user_id=?", (user_id,))).fetchone()
    return str(row[0]) if row else None


async def set_user_status(user_id: int, status: str) -> None:
    async with _db() as db:
        await db.execute("UPDATE users SET status=? WHERE user_id=?", (status, user_id))
        await db.commit()


async def link_user_group(user_id: int, group_id: int) -> None:
    sql = (
        "INSERT INTO users(user_id, group_id, status, linked_at, chat_number) "
        "VALUES(?, ?, 'active', CURRENT_TIMESTAMP, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "group_id=excluded.group_id, status='active', linked_at=CURRENT_TIMESTAMP"
    )
    try:
        async with _db() as db:
            row = await (await db.execute("SELECT chat_number FROM users WHERE user_id=?", (user_id,))).fetchone()
            if row and row[0] is not None:
                chat_number = int(row[0])
            else:
                max_row = await (await db.execute("SELECT COALESCE(MAX(chat_number),0) FROM users")).fetchone()
                chat_number = int(max_row[0]) + 1
            await db.execute(sql, (user_id, group_id, chat_number))
            await db.commit()
        log.info("link_user_group success: user_id=%s group_id=%s", user_id, group_id)
    except Exception as e:
        log.error("link_user_group failed: user_id=%s group_id=%s error=%s", user_id, group_id, e)
        raise


async def get_group_for_user(user_id: int) -> Optional[int]:
    async with _db() as db:
        row = await (
            await db.execute(
                "SELECT group_id FROM users WHERE user_id=? AND status='active'",
                (user_id,),
            )
        ).fetchone()
    return int(row[0]) if row else None


async def get_user_by_group(group_id: int) -> Optional[int]:
    sql = "SELECT user_id FROM users WHERE group_id=? AND status='active'"
    async with _db() as db:
        row = await (await db.execute(sql, (group_id,))).fetchone()
    if row:
        user_id = int(row[0])
        log.info("get_user_by_group found: group_id=%s user_id=%s", group_id, user_id)
        return user_id
    log.warning("get_user_by_group not found: group_id=%s", group_id)
    return None
# END REGION AI


# REGION AI: mailings helpers
async def enqueue_mailing(job: Dict[str, Any]) -> int:
    async with _db() as db:
        cur = await db.execute(
            "INSERT INTO mailings(chat_id, type, file_id, text, run_at, status, error) VALUES (?,?,?,?,?,?,?)",
            (
                job.get("chat_id"),
                job.get("type"),
                job.get("file_id"),
                job.get("text"),
                int(job.get("run_at") or 0),
                "pending",
                job.get("error"),
            ),
        )
        await db.commit()
        return int(cur.lastrowid)
# END REGION AI
