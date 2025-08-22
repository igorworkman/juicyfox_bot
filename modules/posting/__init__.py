# modules/posting/__init__.py
from __future__ import annotations
from contextlib import suppress

# Экспортируем только Router (для apps.bot_core.routers.register)
with suppress(Exception):
    from .handlers import router  # type: ignore

__all__ = ["router"]
