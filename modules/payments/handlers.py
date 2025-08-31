from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from modules.common.i18n import tr
from modules.constants.currencies import CURRENCIES
from modules.ui_membership.chat_keyboards import chat_currency_kb
from modules.ui_membership.keyboards import vip_currency_kb
from shared.utils.lang import get_lang


router = Router()


@router.callback_query(F.data == "cancel")
async def cancel_payment(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle invoice cancellation and restore full tariff description with currency menu."""
    lang = get_lang(callback.from_user)
    data = await state.get_data()
    plan_cb = data.get("plan_callback")
    plan_name = data.get("plan_name")
    price = data.get("price")
    period = data.get("period")

    if not plan_cb or price is None:
        await callback.answer(tr(lang, "nothing_cancel"), show_alert=True)
        return

    # Determine the text and keyboard to restore based on the plan callback
    if plan_cb.startswith("vipay"):
        text = tr(lang, "vip_secret_desc")
        kb = vip_currency_kb(lang)
    elif plan_cb.startswith("paymem:"):
        _, _, plan_code = plan_cb.partition(":")
        text = tr(lang, "choose_cur", amount=price)
        kb = chat_currency_kb(plan_code, lang)
    else:
        builder = InlineKeyboardBuilder()
        for title, code in CURRENCIES:
            builder.button(text=title, callback_data=f"{plan_cb}:{code}")
        builder.button(text=tr(lang, "btn_back"), callback_data="ui:back")
        builder.adjust(2, 2, 2, 2, 1)
        text = tr(
            lang,
            "tariff_desc",
            plan_name=plan_name or "",
            price=price,
            period=period or 0,
        )
        kb = builder.as_markup()

    # Replace the invoice with the original tariff description and currency menu
    await callback.message.edit_text(text, reply_markup=kb)

