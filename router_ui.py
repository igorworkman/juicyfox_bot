from aiogram import Router
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext


router = Router()


@router.message(lambda msg: msg.text == "SEE YOU MY CHAT💬")
async def handle_chat_btn(msg: Message, state: FSMContext):
    lang = msg.from_user.language_code
    await state.set_state(ChatGift.plan)
    await msg.answer(
        tr(lang, 'chat_access'),
        reply_markup=chat_plan_kb(lang)
    )


@router.message(lambda msg: msg.text == "💎 Luxury Room – 15$")
async def luxury_room_reply(msg: Message):
    lang = msg.from_user.language_code
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f'payc:club:{c}')
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    await msg.answer(tr(lang, 'luxury_room_desc'), reply_markup=kb.as_markup())


@router.message(lambda msg: msg.text == "❤️‍🔥 VIP Secret – 35$")
async def vip_secret_reply(msg: Message):
    lang = msg.from_user.language_code
    await msg.answer(
        tr(lang, 'vip_secret_desc'),
        reply_markup=vip_currency_kb()
    )

