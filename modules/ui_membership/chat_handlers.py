from __future__ import annotations

from typing import Any, Optional

from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from modules.common.i18n import tr
from modules.constants.currencies import CURRENCIES
from modules.constants.prices import CHAT_PRICES_USD
from modules.payments import create_invoice
from shared.utils.lang import get_lang

from .chat_keyboards import chat_tariffs_kb, chat_currency_kb

router = Router()

CURRENCY_CODES = {code.upper() for _, code in CURRENCIES}

PLAN_ALIAS = {"7d": "chat_7", "15d": "chat_15", "30d": "chat_30"}


def _invoice_url(inv: Any) -> Optional[str]:
    if isinstance(inv, dict):
        return inv.get("pay_url") or inv.get("url")
    if isinstance(inv, str):
        return inv
    return None


# prices in USD for chat access plans
CHAT_PRICES_USD = {"7d": 5, "15d": 9, "30d": 15}


@router.callback_query(F.data.in_({"ui:chat", "chat"}))
async def show_chat(cq: CallbackQuery) -> None:
    lang = get_lang(cq.from_user)
    await cq.message.edit_text(
        tr(lang, "chat_access"),
        reply_markup=chat_tariffs_kb(lang),
    )


@router.callback_query(F.data.startswith("chatplan:"))
async def choose_chat_currency(cq: CallbackQuery) -> None:
    lang = get_lang(cq.from_user)
    _, _, plan = cq.data.partition("chatplan:")
    plan_code = PLAN_ALIAS.get(plan.strip())
    if not plan_code:
        await cq.answer("Unknown plan", show_alert=True)
        return
    amount = CHAT_PRICES_USD.get(plan_code)
    if amount is None:
        await cq.answer("Unknown plan", show_alert=True)
        return
    await cq.message.edit_text(
        tr(lang, "choose_cur", amount=amount),
        reply_markup=chat_currency_kb(plan_code, lang),
    )


@router.callback_query(F.data.startswith("paymem:"))
async def paymem_currency(cq: CallbackQuery) -> None:
    """Handle chat membership payment with selected currency."""
    lang = get_lang(cq.from_user)
    _, _, payload = cq.data.partition("paymem:")
    plan_code, _, asset = payload.partition(":")
    asset = asset.strip().upper()

    if asset not in CURRENCY_CODES:
        await cq.answer("Unsupported currency", show_alert=True)
        return

    amount = CHAT_PRICES_USD.get(plan_code)
    if amount is None:
        await cq.answer("Unknown plan", show_alert=True)
        return

    inv = await create_invoice(
        user_id=cq.from_user.id,
        plan_code=plan_code,
        amount_usd=float(amount),
        asset=asset,
        meta={"plan": plan_code, "asset": asset},
    )

    url = _invoice_url(inv)
    await cq.message.answer(tr(lang, "invoice_created"))
    if url:
        await cq.message.answer(url)
    kb = InlineKeyboardBuilder()
    kb.button(text=tr(lang, "btn_back"), callback_data="ui:back")
    await cq.message.answer(tr(lang, "back"), reply_markup=kb.as_markup())
