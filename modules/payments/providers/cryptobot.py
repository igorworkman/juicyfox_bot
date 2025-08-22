# modules/payments/providers/cryptobot.py
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

import aiohttp

from .. import InvoiceResponse, ProviderError

log = logging.getLogger("juicyfox.payments.providers.cryptobot")

CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")
CRYPTOBOT_API = os.getenv("CRYPTOBOT_API", "https://pay.crypt.bot/api")

STATUS_MAP = {
    "paid": "paid",
    "expired": "expired",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "active": "pending",
}


class CryptobotProvider:
    async def create_invoice(self, amount_usd: float, title: str, meta: Dict[str, Any]) -> InvoiceResponse:
        if not CRYPTOBOT_TOKEN:
            raise ProviderError("CRYPTOBOT_TOKEN is not set")

        payload = {
            "amount": f"{amount_usd:.2f}",
            "currency": "USD",
            "description": title[:200],
            "payload": json.dumps(meta, ensure_ascii=False),
        }
        headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
        timeout = aiohttp.ClientTimeout(total=20)

        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as sess:
            async with sess.post(f"{CRYPTOBOT_API}/createInvoice", json=payload) as resp:
                text = await resp.text()
                try:
                    data = json.loads(text)
                except Exception:
                    log.error("cryptobot non-JSON response: %s %s", resp.status, text[:500])
                    raise ProviderError(f"cryptobot invalid response (status={resp.status})")

                if resp.status != 200 or not data or not data.get("ok"):
                    log.error("cryptobot error resp=%s body=%s", resp.status, text[:500])
                    raise ProviderError(f"cryptobot error: status={resp.status}, body={text[:200]}")

                res = data.get("result") or {}
                return {
                    "provider": "cryptobot",
                    "invoice_id": str(res.get("invoice_id") or res.get("id") or ""),
                    "pay_url": res.get("pay_url") or res.get("bot_invoice_url") or "",
                }

    def normalize_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        inv = payload.get("invoice") or {}
        meta: Dict[str, Any] = {}
        raw_meta = inv.get("payload")
        if isinstance(raw_meta, str):
            try:
                meta = json.loads(raw_meta)
            except Exception:
                log.warning("cryptobot webhook: bad payload JSON: %r", raw_meta)
                meta = {}

        raw_status = (inv.get("status") or "").lower()
        status = STATUS_MAP.get(raw_status, "unknown")

        return {
            "provider": "cryptobot",
            "invoice_id": str(inv.get("invoice_id") or inv.get("id") or ""),
            "status": status,
            "amount": float(inv.get("amount") or 0),
            "currency": inv.get("currency") or "USD",
            "meta": meta,
        }
