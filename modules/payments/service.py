# modules/payments/service.py
from __future__ import annotations

import os
import json
import logging
from typing import Any, Dict, Optional

import aiohttp

from . import InvoiceResponse, ProviderError

log = logging.getLogger("juicyfox.payments.service")

# --- Провайдеры / ENV ---
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")
CRYPTOBOT_API = os.getenv("CRYPTOBOT_API", "https://pay.crypt.bot/api")
PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "cryptobot").lower()

# Нормализуем статусы к единому виду
STATUS_MAP = {
    "paid": "paid",
    "expired": "expired",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "active": "pending",
}


async def _cryptobot_convert_amount(amount_usd: float, asset: str) -> float:
    """Convert amount in USD to selected asset using CryptoBot rates."""
    if asset.upper() == "USD":
        return amount_usd
    if not CRYPTOBOT_TOKEN:
        raise ProviderError("CRYPTOBOT_TOKEN is not set")
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as sess:
        log.info(
            "cryptobot getExchangeRates: asset=%s amount_usd=%s",
            asset,
            amount_usd,
        )
        async with sess.get(f"{CRYPTOBOT_API}/getExchangeRates") as resp:
            text = await resp.text()
            try:
                data = json.loads(text)
            except Exception:
                log.error(
                    "cryptobot getExchangeRates non-JSON response: %s %s",
                    resp.status,
                    text[:500],
                )
                raise ProviderError(
                    f"cryptobot invalid response (status={resp.status})"
                )
            if resp.status != 200 or not data or not data.get("ok"):
                log.error(
                    "cryptobot getExchangeRates error resp=%s body=%s",
                    resp.status,
                    text[:500],
                )
                raise ProviderError(
                    f"cryptobot error: status={resp.status}, body={text[:200]}"
                )
            rate: Optional[float] = None
            for item in data.get("result", []):
                if item.get("source") == asset.upper() and item.get("target") == "USD":
                    try:
                        rate = float(item.get("rate") or 0)
                    except (TypeError, ValueError):
                        rate = None
                    break
            if not rate:
                raise ProviderError(f"cryptobot exchange rate not found for {asset}")
            return amount_usd / rate


async def _cryptobot_create_invoice(
    amount_usd: float,
    title: str,
    meta: Dict[str, Any],
    asset: str,
) -> InvoiceResponse:
    if not CRYPTOBOT_TOKEN:
        raise ProviderError("CRYPTOBOT_TOKEN is not set")
    amount = await _cryptobot_convert_amount(amount_usd, asset)
    payload = {
        "amount": f"{amount:.2f}",
        "asset": asset.upper(),
        "description": title[:200],
        "payload": json.dumps(meta, ensure_ascii=False),
    }
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}

    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as sess:
        log.info(
            "cryptobot createInvoice: asset=%s amount=%s (usd=%s)",
            asset,
            payload["amount"],
            amount_usd,
        )
        async with sess.post(f"{CRYPTOBOT_API}/createInvoice", json=payload) as resp:
            # Диагностика на случай неожиданных ответов
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


# --- Публичный API сервиса ---

async def create_invoice(
    user_id: int,
    plan_code: str,
    amount_usd: float,
    meta: Dict[str, Any],
    asset: str = "USD",
) -> InvoiceResponse:
    """
    Создаёт счёт через выбранного провайдера (ENV PAYMENT_PROVIDER, по умолчанию cryptobot).
    Возвращает dict: {pay_url, provider, invoice_id}.
    Параметр ``asset`` передаётся напрямую провайдеру (например, ``TON``).
    """
    title = f"{plan_code} for user {user_id}"
    merged_meta = {**meta, "user_id": user_id, "plan_code": plan_code}

    if PAYMENT_PROVIDER == "cryptobot":
        inv = await _cryptobot_create_invoice(
            amount_usd=amount_usd,
            title=title,
            meta=merged_meta,
            asset=asset,
        )
    else:
        raise ProviderError(f"unknown PAYMENT_PROVIDER={PAYMENT_PROVIDER}")

    log.info("invoice created: provider=%s id=%s plan=%s user=%s",
             inv.get("provider"), inv.get("invoice_id"), plan_code, user_id)
    return inv


def normalize_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Унификация вебхука провайдера.
    Выходной формат:
    {
      "provider": "...",
      "invoice_id": "...",
      "status": "paid" | "pending" | "expired" | "cancelled" | "unknown",
      "amount": 25.0,
      "currency": "USD",
      "meta": {...}
    }
    """
    # CryptoBot формат: {"update_id":..., "invoice": {...}}
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
        "currency": inv.get("asset") or inv.get("currency") or "USD",
        "meta": meta,
    }
