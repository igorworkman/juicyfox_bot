qjmeyx-codex/add-prometheus-metrics-integration
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
import asyncio
from juicyfox_bot_single import main as run_bot

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from aiogram.types import Update
from juicyfox_bot_single import main as run_bot, dp, bot_pool

from .check_logs import get_logs_clean, get_logs_full
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

app = FastAPI(default_response_class=JSONResponse)

@app.get("/logs")
async def full_logs():
    return await get_logs_full()

@app.get("/logs/clean")
async def clean_logs():
    return await get_logs_clean()

@app.get("/metrics")
async def metrics() -> Response:
    """Expose Prometheus metrics."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.on_event("startup")
async def startup_event():
    await run_bot()


@app.post("/bot/{bot_id}/webhook")
async def telegram_webhook(bot_id: str, request: Request):
    update = Update.model_validate(await request.json(), context={"bot": bot_pool[bot_id]})
    await dp.feed_update(bot_pool[bot_id], update)
    return {"ok": True}

@app.get("/")
async def root():
    return {"message": "FastAPI работает! 🎉"}
