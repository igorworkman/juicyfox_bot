from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from modules.common.i18n import tr
from shared.utils.lang import get_lang


from .chat_keyboards import membership_currency_kb

router = Router()

# Mapping of chat plans (days) to their price in USD
CHAT_PLANS = {7: 5, 15: 9, 30: 15}


@router.callback_query(F.data.startswith("chatplan:"))
async def choose_chat_currency(cq: CallbackQuery) -> None:
    """Show currency selection after user picks a chat plan."""
    _, _, days_str = cq.data.partition("chatplan:")
    if not days_str.isdigit():
        await cq.answer("Unknown plan", show_alert=True)
        return

    days = int(days_str)
    price = CHAT_PLANS.get(days)
    if price is None:
        await cq.answer("Unknown plan", show_alert=True)
        return

    lang = get_lang(cq.from_user)
    plan_code = f"chat_{days}"
    kb = membership_currency_kb(plan_code, lang)
    await cq.message.edit_text(tr(lang, "choose_cur", amount=price), reply_markup=kb)

from .chat_keyboards import chat_tariffs_kb

router = Router()


@router.callback_query(F.data.in_({"ui:chat", "chat"}))
async def show_chat(cq: CallbackQuery) -> None:
    lang = get_lang(cq.from_user)
    await cq.message.edit_text(
        tr(lang, "chat_access"),
        reply_markup=chat_tariffs_kb(lang),
    )

