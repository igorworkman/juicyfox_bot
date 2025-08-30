from aiogram import Router

from .handlers import router as main_router
from .chat_handlers import router as chat_router

router = Router()
router.include_router(main_router)
router.include_router(chat_router)

__all__ = ("router",)
