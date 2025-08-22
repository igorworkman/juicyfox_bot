# modules/payments/__init__.py
"""
Payments package (Plan A).

Стабильный публичный API:
    - create_invoice(...)
    - normalize_webhook(payload)

Обычно используем так:
    from modules.payments import create_invoice, normalize_webhook
"""

from __future__ import annotations
from typing import Any, Dict, TypedDict


class InvoiceResponse(TypedDict, total=False):
    pay_url: str
    url: str
    provider: str
    invoice_id: str


class InvoiceRequest(TypedDict, total=False):
    user_id: int
    plan_code: str
    amount_usd: float
    meta: Dict[str, Any]


class ProviderError(Exception):
    """Исключение уровня платёжного провайдера/сервиса."""


# Пытаемся импортировать реальную реализацию из service.py.
# Если её ещё нет, даём мягкие заглушки с понятной ошибкой.
try:  # pragma: no cover
    from .service import create_invoice, normalize_webhook  # type: ignore
except Exception:  # pragma: no cover
    async def create_invoice(*args, **kwargs) -> InvoiceResponse:  # type: ignore
        raise ProviderError("payments.service.create_invoice is not implemented yet")

    def normalize_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore
        raise ProviderError("payments.service.normalize_webhook is not implemented yet")


__all__ = [
    "create_invoice",
    "normalize_webhook",
    "ProviderError",
    "InvoiceRequest",
    "InvoiceResponse",
]
