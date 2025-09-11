# REGION AI: imports
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, List

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


# REGION AI: select users
async def _select_users(segment: str) -> List[int]:
    if segment == "all":
        return [int(u["user_id"]) for u in await repo.get_all_relay_users()]
    async with _db() as db:
        cur = await db.execute("SELECT user_id FROM users WHERE status=?", (segment,))
        return [int(r[0]) for r in await cur.fetchall()]
# END REGION AI

async def main() -> None:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN required")
    bot = Bot(TOKEN)
    try:
        while True:
            try:
                async with _db() as db:
                    cur = await db.execute(
                        "SELECT id, type, text, file_id, chat_id, segment FROM mailings "
                        "WHERE status='pending' AND run_at<=?",
                        (int(time.time()),),
                    )
                    mailings = [
                        {
                            "id": r[0],
                            "type": r[1],
                            "text": r[2],
                            "file_id": r[3],
                            "chat_id": r[4] or "broadcast",
                            "segment": r[5] or "all",
                        }
                        for r in await cur.fetchall()
                    ]
                if not mailings:
                    await asyncio.sleep(10)
                    continue
                for m in mailings:
                    is_personal = m.get("chat_id") != "broadcast"
                    users = [int(m["chat_id"])] if is_personal else await _select_users(m.get("segment", "all"))
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
                        status = "done" if fail == 0 else ("failed" if ok == 0 else "partial")
                        await db.execute(
                            "UPDATE mailings SET status=? WHERE id=?",
                            (status, m["id"]),
                        )
                        await db.commit()
                    report = (
                        f"📤 Персональная рассылка {m['id']} → {m['chat_id']}: {ok} доставлено, {fail} ошибок"
                        if is_personal
                        else f"📤 Рассылка {m['id']}: {ok} доставлено, {fail} ошибок, всего {len(users)}"
                    )
                    log.info(report)
                    if ADMIN:
                        await bot.send_message(ADMIN, report)
            except Exception as e:  # pragma: no cover
                log.exception("loop error: %s", e)
            await asyncio.sleep(10)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
# END REGION AI
