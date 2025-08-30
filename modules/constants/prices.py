import os

# Default prices in USD for various plans
VIP_PRICE_USD = float(os.getenv("VIP_30D_USD", "25"))

CHAT_PRICES_USD = {
    "chat_7": float(os.getenv("CHAT_7D_USD", "5")),
    "chat_15": float(os.getenv("CHAT_15D_USD", "9")),
    "chat_30": float(os.getenv("CHAT_30D_USD", "15")),
}

__all__ = ("VIP_PRICE_USD", "CHAT_PRICES_USD")
