from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from aiogram.types import Update
from juicyfox_bot_single import (
    main as run_bot,
    dp,
    bot_pool,
    router_pay,
    router_donate,
    router_history,
    router_ui,
)
import logging

log = logging.getLogger(__name__)

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
    log.info("Starting bot from API startup event")
    for router, name in [
        (router_pay, "router_pay"),
        (router_donate, "router_donate"),
        (router_history, "router_history"),
        (router_ui, "router_ui"),
    ]:
        dp.include_router(router)
        log.info("Registered %s", name)
    await run_bot()
    log.info("Bot started from API startup event")
    log.info("FastAPI server running")


@app.post("/bot/{bot_id}/webhook")
async def telegram_webhook(bot_id: str, request: Request):
    data = await request.json()
    log.info("Incoming update for bot %s: %s", bot_id, data)
    update = Update.model_validate(data, context={"bot": bot_pool[bot_id]})
    await dp.feed_update(bot_pool[bot_id], update)
    return {"ok": True}

@app.get("/")
async def root():
    return {"message": "FastAPI работает! 🎉"}
