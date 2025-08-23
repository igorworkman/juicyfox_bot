# api/main.py
from fastapi import FastAPI

# единообразные импорты роутеров
from api.webhook import router as webhook_router      # POST /bot/{bot_id}/webhook
from api.payments import router as payments_router    # POST /payments/<provider>
from api.health import router as health_router        # /healthz, /readyz
from api.check_logs import logs_router                # /logs, /logs/clean

app = FastAPI(title="JuicyFox API", version="1.0.0")

# регистрация маршрутов
app.include_router(webhook_router,  prefix="/bot")
app.include_router(payments_router, prefix="/payments")
app.include_router(health_router)
app.include_router(logs_router)
