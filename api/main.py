from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
import asyncio
from juicyfox_bot_single import main as run_bot
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
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())

@app.get("/")
async def root():
    return {"message": "FastAPI работает! 🎉"}
