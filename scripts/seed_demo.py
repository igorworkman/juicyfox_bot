#!/usr/bin/env python3
"""Seed demo data for JuicyFox (Plan A).

This script inserts sample data into the bot's SQLite database to
facilitate local development and testing.  It is intentionally kept
simple and may be extended to seed additional tables depending on
your use cases.  The inserted data corresponds to the default
schema defined in ``shared.db.repo`` (messages, streaks,
payment_events, access_grants).

Usage::

    python scripts/seed_demo.py --bot-id sample

By default, it looks for the database at ``/app/data/<bot_id>.sqlite``.
Ensure that the database and schema exist (e.g. by running the bot
once) before seeding.  The script will exit early if the expected
tables are not present.
"""

import argparse
import os
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo data into the JuicyFox database")
    parser.add_argument("--bot-id", default="sample", help="Bot ID whose database to seed")
    parser.add_argument("--db-path", help="Path to the SQLite DB (overrides default)")
    args = parser.parse_args()

    db_path = args.db_path or f"/app/data/{args.bot_id}.sqlite"
    db_file = Path(db_path)
    if not db_file.exists():
        raise SystemExit(
            f"Database file {db_file} does not exist. Run the bot once to initialize it."
        )

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    # Detect which tables are available in the schema
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    required_tables = {"messages", "streaks", "payment_events", "access_grants"}
    if not required_tables.issubset(tables):
        missing = required_tables - tables
        conn.close()
        raise SystemExit(
            f"Database schema is incomplete; missing tables: {', '.join(sorted(missing))}. "
            "Run the bot once to initialize the database."
        )

    print(f"Seeding demo data into {db_file}...")

    # Insert demo messages: one incoming and one outgoing text message
    try:
        cur.execute(
            "INSERT INTO messages (user_id, direction, type, text, ts) VALUES (?,?,?,?,strftime('%s','now'))",
            (12345, "in", "text", "Hello from demo user!"),
        )
        cur.execute(
            "INSERT INTO messages (user_id, direction, type, text, ts) VALUES (?,?,?,?,strftime('%s','now'))",
            (12345, "out", "text", "Reply from bot!"),
        )
    except Exception:
        pass

    # Insert or update a demo streak count
    try:
        cur.execute(
            "INSERT OR REPLACE INTO streaks (user_id, count) VALUES (?, ?)",
            (12345, 3),
        )
    except Exception:
        pass

    # Insert a demo payment event
    try:
        cur.execute(
            "INSERT INTO payment_events (provider, invoice_id, status, amount, currency, meta)"
            " VALUES (?,?,?,?,?,?)",
            ("cryptobot", "demo123", "paid", 15.0, "USD", "{\"demo\": true}"),
        )
    except Exception:
        pass

    # Optionally grant access (if access_grants table exists)
    try:
        cur.execute(
            "INSERT INTO access_grants (user_id, level, granted_at) VALUES (?,?,strftime('%s','now'))",
            (12345, "vip"),
        )
    except Exception:
        pass

    conn.commit()
    conn.close()
    print("Demo data inserted.")


if __name__ == "__main__":
    main()
