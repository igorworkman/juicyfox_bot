from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from modules.common.i18n import tr
from shared.utils.lang import get_lang

from .chat_keyboards import chat_tariffs_kb

router = Router()


@router.callback_query(F.data.in_({"ui:chat", "chat"}))
async def show_chat(cq: CallbackQuery) -> None:
    lang = get_lang(cq.from_user)
    await cq.message.edit_text(
        tr(lang, "chat_access"),
        reply_markup=chat_tariffs_kb(lang),
    )
