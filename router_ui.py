from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

router = Router()


@router.message(Command('cancel'))
async def cancel_any(msg: Message, state: FSMContext):
    """Команда /cancel сбрасывает текущее состояние и возвращает меню"""
    from juicyfox_bot_single import tr, cmd_start

    if await state.get_state():
        await state.clear()
        await msg.answer(tr(msg.from_user.language_code, 'cancel'))
        await cmd_start(msg, state)
    else:
        await msg.answer(tr(msg.from_user.language_code, 'nothing_cancel'))
