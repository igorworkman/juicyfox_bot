"""History module for JuicyFox (Plan A)

This package exposes a single `router` object for use with aiogram
Dispatcher.  It is intentionally lightweight: all logic lives in
``handlers.py``.  Importing this package will attempt to import
``handlers.router`` and expose it via ``__all__``.  If the import
fails (for example, if the optional history feature is disabled or
missing dependencies), it will be silently ignored so that the rest
of the bot can continue to function.
"""

from __future__ import annotations

from contextlib import suppress

__all__ = ["router"]

# Attempt to import the router from handlers.  If it fails for any
# reason (e.g. missing aiogram), fail silently so that optional
# modules can be omitted without breaking the bot.
with suppress(Exception):
    from .handlers import router  # type: ignore  # pragma: no cover
