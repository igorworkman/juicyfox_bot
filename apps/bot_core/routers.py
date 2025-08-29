# apps/bot_core/routers.py
"""
Реестр модульных Router'ов aiogram (План A).
Использование:
    from apps.bot_core.routers import register as register_routers
    register_routers(dp, cfg)   # cfg может быть dataclass, dict, Namespace или None
"""

from contextlib import suppress
from typing import Any

from aiogram import Router


router = Router()


def _get_feature(cfg: Any, name: str, default: bool) -> bool:
    """Безопасно получить флаг features.<name> из cfg (dataclass | dict | obj)."""
    if cfg is None:
        return default
    # dataclass/obj со вложенным features
    with suppress(Exception):
        features = getattr(cfg, "features")
        val = getattr(features, name)
        if isinstance(val, bool):
            return val
    # dict со вложенным features
    with suppress(Exception):
        features = cfg.get("features") if isinstance(cfg, dict) else None
        if isinstance(features, dict):
            val = features.get(name, default)
            if isinstance(val, bool):
                return val
    # прямой доступ (cfg.posting_enabled и т.п.)
    with suppress(Exception):
        val = getattr(cfg, name)
        if isinstance(val, bool):
            return val
    return default


def register(dp, cfg: Any = None) -> None:
    """
    Подключает модульные роутеры.
    Всегда: ui_membership.
    По флагам (по умолчанию True/True/False): posting/chat_relay/history.
    """
    dp.include_router(router)

    # UI / меню / донаты / VIP / чат — базовый модуль
    with suppress(Exception):
        from modules.ui_membership.handlers import router as ui_router
        dp.include_router(ui_router)

    # Планирование и постинг
    if _get_feature(cfg, "posting_enabled", True):
        with suppress(Exception):
            from modules.posting.handlers import router as posting_router
            dp.include_router(posting_router)

    # Пересылка в чат/из чата
    if _get_feature(cfg, "chat_enabled", True):
        with suppress(Exception):
            from modules.chat_relay.handlers import router as chat_router
            dp.include_router(chat_router)

    # История/архив (опционально, обычно выключено)
    if _get_feature(cfg, "history_enabled", False):
        with suppress(Exception):
            from modules.history.handlers import router as history_router
            dp.include_router(history_router)
