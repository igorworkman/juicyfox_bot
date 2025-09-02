from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from modules.common.i18n import tr
from modules.ui_membership.chat_keyboards import chat_currency_kb
from modules.ui_membership.keyboards import vip_currency_kb
from shared.utils.lang import get_lang
from shared.db.repo import get_active_invoice, delete_active_invoice


log = logging.getLogger("juicyfox.payments.handlers")
router = Router()


@router.callback_query(F.data == "cancel")
async def cancel_payment(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle invoice cancellation and restore currency selection."""
    lang = get_lang(callback.from_user)
    invoice = await get_active_invoice(callback.from_user.id)
    log.debug("Active invoice for user %s: %s", callback.from_user.id, invoice)
    if not invoice:
        await callback.answer(tr(lang, "nothing_cancel"), show_alert=True)
        return

    await delete_active_invoice(callback.from_user.id)
    plan_code = invoice["plan_code"]
    plan_callback = invoice.get("plan_callback") or ""

    if plan_callback.startswith("vipay") or plan_code.startswith("vip"):
        desc = tr(lang, "vip_club_description")
        kb = vip_currency_kb(lang)
    else:
        desc = tr(lang, "choose_cur", amount=invoice.get("price"))
        kb = chat_currency_kb(plan_code, lang)

    await state.clear()
    await state.update_data(
        plan_name=invoice.get("plan_name"),
        price=invoice.get("price"),
        period=invoice.get("period"),
        plan_callback=plan_callback,
        plan_code=plan_code,
    )

    await callback.message.edit_text(desc, reply_markup=kb)
