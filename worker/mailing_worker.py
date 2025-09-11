# REGION AI: imports
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict

from aiogram import Bot
from shared.db import repo
from shared.db.repo import _db
# END REGION AI

# REGION AI: mailing worker
log = logging.getLogger("juicyfox.mailing.worker")
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN = int(os.getenv("ADMIN_CHAT_ID", "0") or 0)

async def _send(bot: Bot, uid: int, m: Dict[str, Any]) -> None:
    typ, text, fid = m["type"], m.get("text"), m.get("file_id")
    if typ == "text":
        await bot.send_message(uid, text or "")
        return
    method = {
        "photo": bot.send_photo,
        "video": bot.send_video,
        "document": bot.send_document,
        "animation": bot.send_animation,
    }.get(typ)
    if not method:
        raise RuntimeError(f"unsupported type: {typ}")
    await method(uid, fid, caption=text)

async def main() -> None:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN required")
    bot = Bot(TOKEN)
    while True:
        try:
            async with _db() as db:
                cur = await db.execute(
                    "SELECT id, type, text, file_id FROM mailings "
                    "WHERE status='pending' AND run_at<=?",
                    (int(time.time()),),
                )
                mailings = [
                    {"id": r[0], "type": r[1], "text": r[2], "file_id": r[3]}
                    for r in await cur.fetchall()
                ]
            if not mailings:
                await asyncio.sleep(10)
                continue
            users = [int(u["user_id"]) for u in await repo.get_all_relay_users()]
            for m in mailings:
                ok = fail = 0
                for i in range(0, len(users), 20):
                    res = await asyncio.gather(
                        *(_send(bot, u, m) for u in users[i : i + 20]),
                        return_exceptions=True,
                    )
                    ok += sum(not isinstance(r, Exception) for r in res)
                    fail += sum(isinstance(r, Exception) for r in res)
                    if i + 20 < len(users):
                        await asyncio.sleep(1)
                async with _db() as db:
                    await db.execute(
                        "UPDATE mailings SET status='done' WHERE id=?",
                        (m["id"],),
                    )
                    await db.commit()
                report = f"mailing {m['id']}: {ok} ok, {fail} fail"
                log.info(report)
                if ADMIN:
                    await bot.send_message(ADMIN, report)
        except Exception as e:  # pragma: no cover
            log.exception("loop error: %s", e)
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
# END REGION AI
