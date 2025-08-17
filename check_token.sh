#!/bin/bash
echo "[INFO] Checking Telegram Bot Token..."

if [ -z "$TELEGRAM_TOKEN" ]; then
  echo "[ERROR] TELEGRAM_TOKEN is not set!"
  exit 1
fi

# Проверка getMe
response=$(curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN/getMe")

echo "[INFO] Telegram API response:"
echo "$response"

if [[ "$response" == *"\"ok\":true"* ]]; then
  echo "[SUCCESS] Bot token is valid ✅"
else
  echo "[FAIL] Bot token invalid or Telegram API not reachable ❌"
fi
