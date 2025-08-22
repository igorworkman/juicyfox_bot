"""Utilities package for JuicyFox (Plan A).

This package bundles various helper modules used across the JuicyFox
codebase.  It exposes submodules for logging, time helpers,
idempotency keys, and optional metrics.  Importing this package
directly will attempt to import its submodules; if a submodule fails
to import (for example, due to missing optional dependencies), it is
silently ignored so that the rest of the application continues to
function.

Usage::

    from shared.utils import logging as logging_utils
    logger = logging_utils.get_logger("my.module", bot_id="123")

The ``__all__`` attribute lists the names of subpackages that are
intended for public use.
"""

from __future__ import annotations

from contextlib import suppress

__all__ = ["logging", "time", "idempotency", "metrics"]

# Attempt to import submodules.  Failures are suppressed to allow
# optional dependencies (e.g. prometheus_client) to be absent.
with suppress(Exception):
    from . import logging  # type: ignore  # noqa: F401
with suppress(Exception):
    from . import time  # type: ignore  # noqa: F401
with suppress(Exception):
    from . import idempotency  # type: ignore  # noqa: F401
with suppress(Exception):
    from . import metrics  # type: ignore  # noqa: F401
