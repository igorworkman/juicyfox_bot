from fastapi import FastAPI
from check_logs import get_logs_clean, get_logs_full
import asyncio
from juicyfox_bot_single import main as run_bot

app = FastAPI()

@app.on_event("startup")
async def start_bot():
    asyncio.create_task(run_bot())

@app.get("/")
async def root():
    return {"message": "FastAPI работает! 🎉"}

@app.get("/logs/clean")
async def clean_logs():
    return await get_logs_clean()

@app.get("/logs")
async def full_logs():
    return await get_logs_full()
