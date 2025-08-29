import json
from pathlib import Path

base = Path(__file__).resolve().parents[2] / "locales"
L10N = {}
for lang in ("ru", "en", "es"):
    try:
        with open(base / f"{lang}.json", "r", encoding="utf-8") as f:
            L10N[lang] = json.load(f)
    except FileNotFoundError:
        L10N[lang] = {}

BUTTONS = {
    "btn_life": "👀 Juicy Life - Free",
    "btn_club": "💎 Luxury Room - 15 $",
    "btn_vip": "❤️‍🔥 VIP Secret - 35 $",
    "btn_chat": "💬 Juicy Chat",
    "btn_donate": "🎁 Custom",
    "btn_see_chat": "SEE YOU MY CHAT💬",
    "btn_back": "⬅️ Back",
    "btn_pay_vip": "💳 Pay VIP",
    "btn_pay_chat": "💳 Pay Chat",
    "reply_placeholder": "Choose an option below:",
}
for lang in ("ru", "en", "es"):
    L10N.setdefault(lang, {}).update(BUTTONS)


def tr(lang: str, key: str, **kwargs) -> str:
    text = L10N.get(lang, {}).get(key, key)
    return text.format(**kwargs) if kwargs else text
