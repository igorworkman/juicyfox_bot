"""Centralized environment configuration for JuicyFox (Plan A).

This module centralizes loading and validation of environment variables
for the JuicyFox bot.  It merges values from the process environment
(os.environ) with optional per‑bot YAML configuration files located
under ``configs/bots/<bot_id>.yaml``.  Aliases for commonly used
variables (e.g. ``CRYPTOBOT_TOKEN`` vs ``CRYPTO_BOT_TOKEN``, ``LIFE_URL`` vs
``LIVE_URL``) are supported out of the box.

Usage::

    from shared.config.env import config
    # Access tokens and settings
    token = config.telegram_token
    chat_id = config.chat_group_id

    # If you need to reload configuration (e.g. after changing
    # environment variables), call reload_config():
    config = reload_config()

The ``Config`` dataclass exposes typed attributes for all supported
settings.  Most attributes are strings or integers; booleans are used
for feature flags.  Values missing from both environment and YAML are
assigned sensible defaults, but critical fields like
``telegram_token`` and ``bot_id`` are required and will raise
``RuntimeError`` if missing.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # YAML support is optional

logger = logging.getLogger("juicyfox.env")


@dataclass
class Features:
    """Feature flags controlling optional modules.

    - ``posting_enabled``: enable the posting scheduler/module.
    - ``chat_enabled``: enable the chat relay module.
    - ``history_enabled``: enable the history/archival module.
    """

    posting_enabled: bool = True
    chat_enabled: bool = True
    history_enabled: bool = False


@dataclass
class Config:
    """Holds all configuration values for the bot.

    Not all fields are mandatory at runtime—only those marked in
    ``__post_init__``.  Other values have defaults and may be omitted
    from your environment or YAML.
    """

    telegram_token: str = ""
    bot_id: str = ""
    base_url: Optional[str] = None
    webhook_url: Optional[str] = None
    db_path: str = "/app/data/juicyfox.sqlite"
    loglevel: str = "INFO"
    model_name: str = "Juicy Fox"
    vip_url: Optional[str] = None
    life_url: Optional[str] = None
    vip_price_usd: float = 35.0
    chat_price_usd: float = 15.0
    chat_group_id: int = 0
    history_group_id: Optional[int] = None
    post_plan_group_id: Optional[int] = None
    life_channel_id: int = 0
    vip_channel_id: int = 0
    log_channel_id: int = 0
    cryptobot_token: str = ""
    cryptobot_api: str = "https://pay.crypt.bot/api"
    post_worker_interval: int = 5
    post_worker_batch: int = 20
    features: Features = field(default_factory=Features)
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate required fields and normalize types."""
        # Required fields
        if not self.telegram_token:
            raise RuntimeError("TELEGRAM_TOKEN is required in environment or YAML config")
        if not self.bot_id:
            raise RuntimeError("BOT_ID is required in environment or YAML config")

        # Normalize optional integer fields that may be provided as strings
        def _ensure_int(value: Any) -> Optional[int]:
            if value is None:
                return None
            try:
                return int(value)
            except Exception:
                return None

        self.chat_group_id = _ensure_int(self.chat_group_id) or 0
        self.history_group_id = _ensure_int(self.history_group_id)
        self.post_plan_group_id = _ensure_int(self.post_plan_group_id)
        self.life_channel_id = _ensure_int(self.life_channel_id) or 0
        self.vip_channel_id = _ensure_int(self.vip_channel_id) or 0
        self.log_channel_id = _ensure_int(self.log_channel_id) or 0
        self.post_worker_interval = _ensure_int(self.post_worker_interval) or 5
        self.post_worker_batch = _ensure_int(self.post_worker_batch) or 20


def _load_yaml_config(bot_id: str) -> Dict[str, Any]:
    """Load per‑bot YAML configuration if available.

    The YAML file is expected at ``configs/bots/<bot_id>.yaml`` relative
    to the project root.  If YAML is unavailable or the file does not
    exist, an empty dict is returned.
    """
    if not yaml:
        return {}
    # Determine path: this file lives at shared/config/env.py, so go up
    # two levels to reach the project root.
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    cfg_path = os.path.join(base_dir, "configs", "bots", f"{bot_id}.yaml")
    if not os.path.exists(cfg_path):
        return {}
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data or {}
    except Exception as e:
        logger.warning("env: failed to load YAML config %s: %s", cfg_path, e)
        return {}


def _get_alias(env: Dict[str, str], *names: str, default: Optional[str] = None) -> Optional[str]:
    """Return the first defined environment variable from ``names``.

    Example::

        _get_alias(os.environ, 'CRYPTOBOT_TOKEN', 'CRYPTO_BOT_TOKEN')

    will return the value of ``CRYPTOBOT_TOKEN`` if set, otherwise the
    value of ``CRYPTO_BOT_TOKEN``.  If neither is set, returns
    ``default``.
    """
    for name in names:
        val = env.get(name)
        if val:
            return val
    return default


def load_config(bot_id: Optional[str] = None) -> Config:
    """Load configuration from environment and optional YAML.

    If ``bot_id`` is not provided, it is taken from the ``BOT_ID``
    environment variable (defaulting to ``sample`` if missing).  The
    loaded configuration is returned as a ``Config`` object.
    """
    env = os.environ
    resolved_bot_id = (bot_id or env.get("BOT_ID") or "sample").strip()
    yaml_data = _load_yaml_config(resolved_bot_id)

    # Extract features from YAML if present
    features_data = yaml_data.get("features", {}) if isinstance(yaml_data, dict) else {}
    features = Features(
        posting_enabled=bool(features_data.get("posting_enabled", True)),
        chat_enabled=bool(features_data.get("chat_enabled", True)),
        history_enabled=bool(features_data.get("history_enabled", False)),
    )

    # Helper to parse numeric YAML overrides; YAML parser may return ints
    def _yaml_int(key: str, default: Optional[int] = None) -> Optional[int]:
        val = yaml_data.get(key) if isinstance(yaml_data, dict) else None
        if isinstance(val, int):
            return val
        try:
            return int(val)
        except Exception:
            return default

    cfg = Config(
        telegram_token=_get_alias(env, "TELEGRAM_TOKEN", default=yaml_data.get("telegram_token", "")),
        bot_id=resolved_bot_id,
        base_url=_get_alias(env, "BASE_URL", default=yaml_data.get("base_url")),
        webhook_url=_get_alias(env, "WEBHOOK_URL", default=yaml_data.get("webhook_url")),
        db_path=_get_alias(env, "DB_PATH", default=yaml_data.get("db_path", "/app/data/juicyfox.sqlite")),
        loglevel=_get_alias(env, "LOGLEVEL", default=yaml_data.get("loglevel", "INFO")),
        model_name=_get_alias(env, "MODEL_NAME", default=yaml_data.get("model_name", "Juicy Fox")),
        vip_url=_get_alias(env, "VIP_URL", default=yaml_data.get("vip_url")),
        # REGION AI: life_url fallback
        # fix: provide default life channel URL
        life_url=_get_alias(
            env,
            "LIFE_URL",
            "LIVE_URL",
            default=yaml_data.get("life_url") or "https://t.me/JuisyFoxOfficialLife",
        ),
        # END REGION AI
        vip_price_usd=float(_get_alias(env, "VIP_PRICE_USD", "VIP_30D_USD", default=yaml_data.get("vip_price_usd", 35))),
        chat_price_usd=float(_get_alias(env, "CHAT_PRICE_USD", "CHAT_30D_USD", default=yaml_data.get("chat_price_usd", 15))),
        chat_group_id=int(_get_alias(env, "CHAT_GROUP_ID", default=_yaml_int("chat_group_id", 0) or 0) or 0),
        history_group_id=_yaml_int("history_group_id") or int(_get_alias(env, "HISTORY_GROUP_ID", default="0") or 0) or None,
        post_plan_group_id=_yaml_int("post_plan_group_id") or int(_get_alias(env, "POST_PLAN_GROUP_ID", default="0") or 0) or None,
        life_channel_id=int(_get_alias(env, "LIFE_CHANNEL_ID", default=_yaml_int("life_channel_id", 0) or 0) or 0),
        vip_channel_id=int(_get_alias(env, "VIP_CHANNEL_ID", default=_yaml_int("vip_channel_id", 0) or 0) or 0),
        log_channel_id=int(_get_alias(env, "LOG_CHANNEL_ID", default=_yaml_int("log_channel_id", 0) or 0) or 0),
        cryptobot_token=_get_alias(env, "CRYPTOBOT_TOKEN", "CRYPTO_BOT_TOKEN", default=yaml_data.get("cryptobot_token", "")),
        cryptobot_api=_get_alias(env, "CRYPTOBOT_API", default=yaml_data.get("cryptobot_api", "https://pay.crypt.bot/api")),
        post_worker_interval=int(_get_alias(env, "POST_WORKER_INTERVAL", default=_yaml_int("post_worker_interval", 5) or 5) or 5),
        post_worker_batch=int(_get_alias(env, "POST_WORKER_BATCH", default=_yaml_int("post_worker_batch", 20) or 20) or 20),
        features=features,
        extra=yaml_data.get("extra", {}) if isinstance(yaml_data, dict) else {},
    )
    # Log summary of loaded configuration for easier debugging
    try:
        logger.info(
            "env: loaded config for bot_id=%s (features: posting=%s chat=%s history=%s)",
            resolved_bot_id,
            cfg.features.posting_enabled,
            cfg.features.chat_enabled,
            cfg.features.history_enabled,
        )
    except Exception:
        # Guard against logging failures (e.g. if logger isn't configured)
        pass
    return cfg


# Load configuration once at import; can be reloaded by calling reload_config().
config: Config = load_config()


def reload_config(bot_id: Optional[str] = None) -> Config:
    """Reload the configuration and update the global ``config`` object.

    Pass ``bot_id`` to override the BOT_ID used for YAML lookup.  The
    returned ``Config`` instance is also stored in ``shared.config.env.config``.
    """
    global config
    config = load_config(bot_id)
    return config
