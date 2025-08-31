import os
from typing import Any, Dict

BOT_ID = os.getenv("BOT_ID", "sample")


def _build_meta(user_id: int, plan_code: str, currency: str) -> Dict[str, Any]:
    """Compose invoice metadata shared across membership flows."""
    return {
        "user_id": user_id,
        "plan_code": plan_code,
        "currency": currency,
        "bot_id": BOT_ID,
    }
