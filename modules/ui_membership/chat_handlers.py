from typing import Any, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from modules.common.i18n import tr
from modules.constants.currencies import CURRENCIES
from modules.constants.prices import CHAT_PRICES_USD
from modules.payments import create_invoice
from shared.utils.lang import get_lang
from shared.db.repo import save_pending_invoice

from .chat_keyboards import chat_tariffs_kb, chat_currency_kb
from .keyboards import chat_invoice_keyboard
from .utils import _build_meta

router = Router()

CURRENCY_CODES = {code.upper() for _, code in CURRENCIES}

PLAN_ALIAS = {"10d": "chat_10d", "20d": "chat_20d", "30d": "chat_30d"}
PLAN_TITLES = {"chat_10d": "Chat 10", "chat_20d": "Chat 20", "chat_30d": "Chat 30"}
PLAN_PRICES = {k: CHAT_PRICES_USD.get(k, v) for k, v in {"chat_10d": 9.0, "chat_20d": 17.0, "chat_30d": 25.0}.items()}


def _invoice_url(inv: Any) -> Optional[str]:
    if isinstance(inv, dict):
        return inv.get("pay_url") or inv.get("url")
    if isinstance(inv, str):
        return inv
    return None


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
    amount = PLAN_PRICES.get(plan_code)
    if amount is None:
        await cq.answer("Unknown plan", show_alert=True)
        return
    await cq.message.edit_text(
        tr(lang, "choose_cur", amount=amount),
        reply_markup=chat_currency_kb(plan_code, lang),
    )


@router.callback_query(F.data.startswith("paymem:"))
async def paymem_currency(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle chat membership payment with selected currency."""
    lang = get_lang(callback.from_user)
    _, _, payload = callback.data.partition("paymem:")
    plan_code, _, asset = payload.partition(":")
    asset = asset.strip().upper()

    if asset not in CURRENCY_CODES:
        await callback.answer("Unsupported currency", show_alert=True)
        return

    amount = PLAN_PRICES.get(plan_code)
    if amount is None:
        await callback.answer("Unknown plan", show_alert=True)
        return

    period = int(plan_code.split("_")[-1]) if plan_code.split("_")[-1].isdigit() else 0

    await state.update_data(
        plan_name=PLAN_TITLES.get(plan_code, plan_code),
        price=float(amount),
        period=period,
        plan_callback=f"paymem:{plan_code}",
    )

    inv = await create_invoice(
        user_id=callback.from_user.id,
        plan_code=plan_code,
        amount_usd=float(amount),
        meta=_build_meta(callback.from_user.id, plan_code, asset),
        asset=asset,
    )
    invoice_id = inv.get("invoice_id") if isinstance(inv, dict) else None
    if invoice_id:
        await state.update_data(invoice_id=invoice_id, currency=asset, plan_code=plan_code)
        await save_pending_invoice(
            callback.from_user.id,
            invoice_id,
            plan_code,
            asset,
            f"paymem:{plan_code}",
            PLAN_TITLES.get(plan_code, plan_code),
            float(amount),
            period,
        )

    url = _invoice_url(inv)
    if url:
        plan_name = PLAN_TITLES.get(plan_code, plan_code)
        await callback.message.edit_text(
            tr(lang, "invoice_message", plan=plan_name, url=url),
            reply_markup=chat_invoice_keyboard(lang, url),
        )
    else:
        await callback.message.edit_text(tr(lang, "inv_err"))
