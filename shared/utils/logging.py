"""Logging utilities for JuicyFox (Plan A).

This module provides helper functions to configure Python's logging
module with a consistent format and to enrich log records with
contextual data (bot ID, module name, correlation ID).  Using
``get_logger()`` yields a ``logging.LoggerAdapter`` that injects
``bot_id``, ``mod_name`` (the logical module name) and ``corr_id`` into each log record.
The ``setup_logging()`` function configures the root logger based on the
``LOGLEVEL`` environment variable and reconfigures logging on repeated calls.

Example::

    from shared.utils.logging import setup_logging, get_logger

    setup_logging()  # configure the root logger once at startup
    logger = get_logger(__name__, bot_id="42", corr_id="abc123")
    logger.info("Hello world")
"""

from __future__ import annotations

import os
import logging
from typing import Optional


def setup_logging(level: Optional[str] = None) -> None:
    """Configure the root logger with a standard format.

    If ``level`` is not provided, it is taken from the ``LOGLEVEL``
    environment variable, defaulting to ``INFO``.  The log format
    includes placeholders for ``asctime`` (timestamp), ``bot_id``,
    ``mod_name``, ``corr_id``, ``levelname`` and ``message``.  If a log
    record does not have one of these attributes, a hyphen ``-`` is
    substituted.  The ``force=True`` parameter reinitializes logging
    configuration if called multiple times.
    """
    lvl = level or os.getenv("LOGLEVEL", "INFO").upper()
    logging.basicConfig(
        level=lvl,
        format=(
            "%(asctime)s | %(bot_id)s | %(mod_name)s | %(corr_id)s | "
            "%(levelname)s | %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
        # Force reconfiguration on repeated calls (Python 3.8+)
        force=True,
    )


class _ContextAdapter(logging.LoggerAdapter):
    """LoggerAdapter that injects bot/module/correlation IDs into records."""

    def __init__(self, logger: logging.Logger, bot_id: str, module: str, corr_id: Optional[str] = None) -> None:
        super().__init__(logger, {})
        self.bot_id = bot_id
        self.module_name = module
        self.corr_id = corr_id or "-"

    def process(self, msg, kwargs):
        extra = kwargs.setdefault("extra", {})
        # Provide defaults; existing values take precedence
        extra.setdefault("bot_id", self.bot_id)
        extra.setdefault("mod_name", self.module_name)
        extra.setdefault("corr_id", self.corr_id)
        return msg, kwargs


def get_logger(module: str, *, bot_id: str, corr_id: Optional[str] = None) -> logging.LoggerAdapter:
    """Return a logger adapter for the given module and bot.

    :param module: The name of the module emitting logs (usually
        ``__name__``).
    :param bot_id: Identifier of the bot instance (used to group logs
        from different bots when running multiple instances).
    :param corr_id: Optional correlation ID for tracing a single
        request or workflow across multiple log entries.
    :returns: A ``logging.LoggerAdapter`` that automatically injects
        ``bot_id``, ``mod_name`` and ``corr_id`` into each log record.
    """
    base_logger = logging.getLogger(module)
    return _ContextAdapter(base_logger, bot_id=str(bot_id), module=module, corr_id=corr_id)
