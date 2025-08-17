
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from utils import tr
# from juicyfox_bot_single import CURRENCIES, create_invoice, tr
from aiogram.filters import Command

from aiogram import Router


from aiogram.types import Message
from aiogram.fsm.context import FSMContext


from aiogram.utils.keyboard import InlineKeyboardBuilder




router = Router()



@router.message(Command('cancel'))
async def cancel_any(msg: Message, state: FSMContext):
    """Команда /cancel сбрасывает текущее состояние и возвращает меню"""
    # from juicyfox_bot_single import tr, cmd_start

    if await state.get_state():
        await state.clear()
        await msg.answer(tr(msg.from_user.language_code, 'cancel'))
        # await cmd_start(msg, state)
    else:
        await msg.answer(tr(msg.from_user.language_code, 'nothing_cancel'))


@router.message(Command("ui_test"))
async def ui_stub(message: Message):
    await message.answer("🖥️ UI модуль временно недоступен.")


class Donate(StatesGroup):
    choosing_currency = State()
    entering_amount = State()


@router.callback_query(F.data == "donate")
async def donate_currency(cq: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f"doncur:{c}")
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    await cq.message.edit_text(
        tr(cq.from_user.language_code, "choose_cur", amount="donate"),
        reply_markup=kb.as_markup(),
    )
    await state.set_state(Donate.choosing_currency)


@router.callback_query(F.data.startswith("doncur:"), Donate.choosing_currency)
async def donate_amount(cq: CallbackQuery, state: FSMContext):
    """Отображаем просьбу ввести сумму + кнопка 🔙 Назад"""
    await state.update_data(currency=cq.data.split(":")[1])
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="don_back")]]
    )
    await cq.message.edit_text(
        tr(cq.from_user.language_code, "don_enter"),
        reply_markup=back_kb,
    )
    await state.set_state(Donate.entering_amount)


@router.callback_query(F.data == "don_back", Donate.entering_amount)
async def donate_back(cq: CallbackQuery, state: FSMContext):
    """Возврат к выбору валюты с кнопкой Назад"""
    await state.set_state(Donate.choosing_currency)
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f"doncur:{c}")
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    await cq.message.edit_text(
    tr(cq.from_user.language_code, "choose_cur", amount="donate")
)


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


"""UI-related handlers and keyboards for JuicyFox bot."""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardBuilder,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from aiogram.fsm.context import FSMContext

router = Router()
log = logging.getLogger(__name__)


def chat_plan_kb(lang: str) -> InlineKeyboardMarkup:
    """Keyboard for selecting chat access duration."""
    from juicyfox_bot_single import tr

    kb = InlineKeyboardBuilder()
    for key, days in [("chat_flower_1", 7), ("chat_flower_2", 15), ("chat_flower_3", 30)]:
        kb.button(text=tr(lang, key), callback_data=f"chatgift:{days}")
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(1)
    return kb.as_markup()


def build_tip_menu(lang: str) -> InlineKeyboardBuilder:
    """Construct the inline tip menu."""
    from juicyfox_bot_single import tr

    kb = InlineKeyboardBuilder()
    kb.button(text=tr(lang, "btn_life"), callback_data="life")
    kb.button(text=tr(lang, "btn_club"), callback_data="pay:club")
    kb.button(text=tr(lang, "btn_vip"), callback_data="pay:vip")
    kb.button(text=tr(lang, "btn_donate"), callback_data="donate")
    kb.button(text="💬 Chat", callback_data="pay:chat")
    kb.adjust(1)
    return kb


def vip_currency_kb() -> InlineKeyboardMarkup:
    """Keyboard with currency options for VIP payments."""
    from juicyfox_bot_single import CURRENCIES

    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f"vipay:{c}")
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    return kb.as_markup()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command and show main menu."""
    from juicyfox_bot_single import LIFE_URL, tr

    log.info("/start handler called for user %s", message.from_user.id)
    if await state.get_state():
        await state.clear()
    lang = message.from_user.language_code
    reply_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="SEE YOU MY CHAT💬")],
            [
                KeyboardButton(text="💎 Luxury Room – 15$"),
                KeyboardButton(text="❤️‍🔥 VIP Secret – 35$")
            ],
        ],
        resize_keyboard=True,
    )

    kb = build_tip_menu(lang)

    await message.answer_photo(
        photo="https://files.catbox.moe/cqckle.jpg",
        caption=tr(lang, "menu", name=message.from_user.first_name),
    )

    await message.answer(
        text=tr(lang, "my_channel", link=LIFE_URL),
        reply_markup=reply_kb,
    )


@router.callback_query(F.data == "life")
async def life_link(cq: CallbackQuery):
    """Show link to the Life channel."""
    from juicyfox_bot_single import LIFE_URL, tr

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(1)
    await cq.message.edit_text(
        tr(cq.from_user.language_code, "life", my_channel=LIFE_URL),
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data == "back")
async def back_to_main(cq: CallbackQuery):
    """Return to the main inline menu."""
    from juicyfox_bot_single import tr

    lang = cq.from_user.language_code
    kb = build_tip_menu(lang)
    await cq.message.edit_text(
        tr(lang, "choose_action"),

        reply_markup=kb.as_markup(),
    )



@router.message(Donate.entering_amount)
async def donate_finish(msg: Message, state: FSMContext):
    """Получаем сумму в USD, создаём счёт и завершаем FSM"""
    text = msg.text.replace(",", ".").strip()
    if not text.replace(".", "", 1).isdigit():
        await msg.reply(tr(msg.from_user.language_code, "don_num"))
        return
    usd = float(text)
    data = await state.get_data()
    cur = data["currency"]
    url = await create_invoice(msg.from_user.id, usd, cur, "JuicyFox Donation", pl="donate")
    if url:
        await msg.answer(f"Счёт на оплату (Donate): {url}")
    else:
        await msg.reply(tr(msg.from_user.language_code, "inv_err"))
    await state.clear()

@router.callback_query(F.data == "tip_menu")
async def tip_menu(cq: CallbackQuery):
    """Send the tip menu as a new message."""
    from juicyfox_bot_single import tr

    lang = cq.from_user.language_code
    kb = build_tip_menu(lang)
    await cq.message.answer(tr(lang, "choose_action"), reply_markup=kb.as_markup())


