#!/bin/bash

# Проверка состояния вебхука у бота
if [ -z "$TELEGRAM_TOKEN" ]; then
  echo "[ERROR] TELEGRAM_TOKEN is not set!"
  exit 1
fi

echo "[INFO] Checking Telegram Webhook..."
RESPONSE=$(curl -s -X GET "https://api.telegram.org/bot$TELEGRAM_TOKEN/getWebhookInfo")

echo "[INFO] Telegram API response:"
echo "$RESPONSE"

if [[ "$RESPONSE" == *"url"* ]]; then
  echo "[SUCCESS] Webhook info retrieved ✅"
else
  echo "[ERROR] Failed to get webhook info ❌"
fi
