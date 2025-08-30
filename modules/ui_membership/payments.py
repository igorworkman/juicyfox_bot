from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from modules.common.i18n import tr
from modules.payments import create_invoice
from shared.utils.lang import get_lang

from .handlers import _build_meta, _invoice_url, VIP_PRICE_USD, CURRENCY_CODES
from .chat_handlers import CHAT_PRICES_USD

router = Router()


@router.callback_query(F.data.startswith("paymem:"))
async def _pay_membership_currency(cq: CallbackQuery) -> None:
    """Generic handler for membership payments.

    Expected callback data format: ``paymem:<plan_code>:<currency>``.
    ``plan_code`` examples: ``vip_30d``, ``chat_7d``.
    """
    lang = get_lang(cq.from_user)
    _, _, rest = cq.data.partition("paymem:")
    plan_code, _, currency = rest.partition(":")
    plan_code = plan_code.strip()
    currency = currency.strip().upper()

    if currency not in CURRENCY_CODES:
        await cq.answer("Unsupported currency", show_alert=True)
        return

    amount_usd: float | None
    if plan_code == "vip_30d":
        amount_usd = float(VIP_PRICE_USD)
    elif plan_code.startswith("chat_"):
        period = plan_code.split("_", 1)[1]
        amount_usd = CHAT_PRICES_USD.get(period)
    else:
        amount_usd = None

    if amount_usd is None:
        await cq.answer("Unknown plan", show_alert=True)
        return

    inv = await create_invoice(
        user_id=cq.from_user.id,
        plan_code=plan_code,
        amount_usd=float(amount_usd),
        meta=_build_meta(cq.from_user.id, plan_code, currency),
        asset=currency,
    )
    url = _invoice_url(inv)
    await cq.message.answer(tr(lang, "invoice_message", plan=plan_code, url=url))
