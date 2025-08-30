
from aiogram import Router

from .handlers import router as main_router
from .chat_handlers import router as chat_router
from .payments import router as payments_router

router = Router()
router.include_router(main_router)
router.include_router(chat_router)
router.include_router(payments_router)

from .handlers import router


__all__ = ("router",)
