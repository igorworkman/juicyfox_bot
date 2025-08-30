from fastapi import FastAPI
from api.webhook import router as webhook_router
from api.payments import router as payments_router
from api.health import router as health_router
from api.check_logs import router as logs_router

app = FastAPI(title="JuicyFox API", version="1.0.0")

# Вебхук БЕЗ префикса, путь ровно /webhook
app.include_router(webhook_router)

# Остальные — как были
app.include_router(payments_router, prefix="/payments")
app.include_router(health_router)
app.include_router(logs_router)

