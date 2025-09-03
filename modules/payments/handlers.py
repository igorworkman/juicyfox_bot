from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
# REGION AI: imports
from aiogram.types import Message, LabeledPrice
from modules.access import grant
# END REGION AI
from modules.common.i18n import tr
from modules.ui_membership.chat_keyboards import chat_currency_kb
from modules.ui_membership.keyboards import vip_currency_kb, donate_currency_keyboard
from shared.utils.lang import get_lang
from shared.db.repo import get_active_invoice, delete_pending_invoice


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
    plan_code = invoice["plan_code"]
    plan_callback = invoice.get("plan_callback") or ""
    fsm_state = await state.get_state()
    deleted_rows = await delete_pending_invoice(invoice["invoice_id"])
    log.info(
        "cancel_payment: user_id=%s invoice_id=%s plan_code=%s state=%s deleted=%s",
        callback.from_user.id,
        invoice["invoice_id"],
        plan_code,
        fsm_state,
        deleted_rows > 0,
    )

    if plan_callback.startswith("vipay") or plan_code.startswith("vip"):
        desc = tr(lang, "vip_club_description")
        kb = vip_currency_kb(lang)
        await state.clear()
        await state.update_data(
            plan_name=invoice.get("plan_name"),
            price=invoice.get("price"),
            period=invoice.get("period"),
            plan_callback=plan_callback,
            plan_code=plan_code,
        )
    elif plan_callback == "donate" or plan_code == "donation":
        from modules.ui_membership.handlers import Donate

        desc = tr(lang, "donate_currency")
        kb = donate_currency_keyboard(lang)
        await state.clear()
        await state.update_data(amount=invoice.get("price"))
        await state.set_state(Donate.choosing_currency)
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


# REGION AI: Telegram Stars payments
@router.callback_query(F.data == "pay_stars")
async def pay_stars(callback: CallbackQuery, state: FSMContext) -> None:
    lang = get_lang(callback.from_user)
    data = await state.get_data()
    plan_code = data.get("plan_code") or "donation"
    purchase = "vip" if plan_code.startswith("vip") else "donate"
    title = data.get("plan_name") or purchase
    amount = int(data.get("price") or 1)
    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=title,
        description=tr(lang, "choose_cur", amount=amount),
        payload=f"{purchase}:{plan_code}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=title, amount=amount * 100)],
    )


@router.message(F.successful_payment)
async def stars_success(message: Message) -> None:
    lang = get_lang(message.from_user)
    payload = message.successful_payment.invoice_payload
    purchase, _, plan_code = payload.partition(":")
    if purchase == "vip":
        await grant(message.from_user.id, plan_code or "vip_30d", bot=message.bot)
        await message.answer(tr(lang, "pay_conf"))
    else:
        await message.answer(tr(lang, "donate_intro_1"))
# END REGION AI
