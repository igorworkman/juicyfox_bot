# modules/payments/providers/__init__.py
from __future__ import annotations

import os
from typing import Any, Dict, Protocol

from .. import InvoiceResponse, ProviderError

PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "cryptobot").lower()


class PaymentsProvider(Protocol):
    async def create_invoice(
        self, amount_usd: float, title: str, meta: Dict[str, Any], currency: str = "USD"
    ) -> InvoiceResponse: ...
    def normalize_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...


def get_provider() -> PaymentsProvider:
    """
    Возвращает адаптер провайдера по ENV PAYMENT_PROVIDER.
    Добавление новых провайдеров = новая ветка elif и импорт.
    """
    if PAYMENT_PROVIDER == "cryptobot":
        from .cryptobot import CryptobotProvider  # локальный импорт
        return CryptobotProvider()
    raise ProviderError(f"unknown PAYMENT_PROVIDER={PAYMENT_PROVIDER}")
