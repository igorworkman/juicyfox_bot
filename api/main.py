from fastapi import FastAPI
from fastapi.responses import JSONResponse
import asyncio
from juicyfox_bot_single import main as run_bot
from check_logs import get_logs_clean, get_logs_full

app = FastAPI(default_response_class=JSONResponse)

@app.get("/logs")
async def full_logs():
    return await get_logs_full()

@app.get("/logs/clean")
async def clean_logs():
    return await get_logs_clean()

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())

@app.get("/")
async def root():
    return {"message": "FastAPI работает! 🎉"}
