from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from modules.common.i18n import tr
from modules.constants.currencies import CURRENCIES
from shared.utils.lang import get_lang


router = Router()


@router.callback_query(F.data == "cancel")
async def cancel_payment(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle invoice cancellation and return to currency menu."""
    lang = get_lang(callback.from_user)
    data = await state.get_data()
    plan_cb = data.get("plan_callback")
    plan_name = data.get("plan_name")
    price = data.get("price")
    period = data.get("period")

    if not plan_cb or not plan_name or price is None or period is None:
        await callback.answer(tr(lang, "nothing_cancel"), show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    for title, code in CURRENCIES:
        kb.button(text=title, callback_data=f"{plan_cb}:{code}")
    kb.button(text=tr(lang, "btn_back"), callback_data="ui:back")
    kb.adjust(2, 2, 2, 2, 1)

    text = tr(
        lang,
        "tariff_desc",
        plan_name=plan_name,
        price=price,
        period=period,
    )

    await callback.message.edit_text(text, reply_markup=kb.as_markup())

