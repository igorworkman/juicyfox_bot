from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
# REGION AI: imports
from aiogram.types import Message, LabeledPrice
from modules.access import grant
# REGION AI: price constants
from modules.constants.prices import VIP_PRICE_USD
# END REGION AI
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
        # REGION AI: choose currency text
        key = "choose_cur_stars" if invoice.get("currency") == "XTR" else "choose_cur_usd"
        desc = tr(lang, key, amount=invoice.get("price"))
        # END REGION AI
        kb = chat_currency_kb(plan_code, lang)
        await state.clear()
        data_key = "stars" if invoice.get("currency") == "XTR" else "price"
        await state.update_data(
            plan_name=invoice.get("plan_name"),
            period=invoice.get("period"),
            plan_callback=plan_callback,
            plan_code=plan_code,
            **{data_key: invoice.get("price")},
        )

    # REGION AI: ensure HTML parse mode for descriptions
    await callback.message.edit_text(desc, reply_markup=kb, parse_mode="HTML")
    # END REGION AI


# REGION AI: Telegram Stars payments
CHAT_STAR_PLANS = {
    "chat_7d": ("Chat 7", 7, 250),
    "chat_15d": ("Chat 15", 15, 450),
    "chat_30d": ("Chat 30", 30, 750),
}


@router.callback_query(F.data.startswith("pay_stars"))
async def pay_stars(callback: CallbackQuery, state: FSMContext) -> None:
    lang = get_lang(callback.from_user)
    data = await state.get_data()
    _, _, plan_code = callback.data.partition(":")
    plan_callback = data.get("plan_callback") or ""
    if plan_code in CHAT_STAR_PLANS:
        title, period, stars = CHAT_STAR_PLANS[plan_code]
        await state.update_data(
            plan_name=title,
            period=period,
            plan_callback=f"paymem:{plan_code}",
            plan_code=plan_code,
            stars=stars,
        )
        purchase = "chat"
    else:
        plan_code = data.get("plan_code") or ""
        if not plan_code and not plan_callback:
            await state.update_data(
                plan_code="vip_30d",
                plan_callback="vip",
                plan_name=f"VIP CLUB - {int(VIP_PRICE_USD)}$",
                stars=int(VIP_PRICE_USD * 100),
            )
            data = await state.get_data()
            plan_code = data.get("plan_code") or ""
            plan_callback = data.get("plan_callback") or ""
        purchase = (
            "vip"
            if plan_callback == "vip" or plan_code.startswith("vip")
            else "donate"
        )
        title = data.get("plan_name") or (
            f"VIP CLUB - {int(VIP_PRICE_USD)}$"
            if purchase == "vip"
            else purchase
        )
        stars = int(data.get("stars") or int(VIP_PRICE_USD * 100))
    await callback.message.answer_invoice(
        title=title,
        description=tr(lang, "stars_payment_desc"),
        payload=f"{purchase}:{plan_code}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=title, amount=stars)],
    )


@router.message(F.successful_payment)
async def stars_success(message: Message) -> None:
    lang = get_lang(message.from_user)
    purchase, _, plan_code = message.successful_payment.invoice_payload.partition(":")
    if purchase in {"vip", "chat"}:
        default_code = "vip_30d" if purchase == "vip" else "chat_7d"
        await grant(message.from_user.id, plan_code or default_code, bot=message.bot)
        await message.answer(tr(lang, "pay_conf"))
    else:
        amount = message.successful_payment.total_amount
        await message.answer(tr(lang, "donate_thanks", amount=amount))
# END REGION AI
