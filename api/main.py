from fastapi import FastAPI
from check_logs import get_logs_clean, get_logs_full
import asyncio
import subprocess

app = FastAPI()

@app.on_event("startup")
async def start_bot():
    # Запускаем juicyfox_bot_single.py как фоновый процесс
    asyncio.create_task(run_bot())

async def run_bot():
    process = await asyncio.create_subprocess_exec(
        "python", "juicyfox_bot_single.py"
    )
    await process.wait()

@app.get("/")
async def root():
    return {"message": "FastAPI работает! 🎉"}

@app.get("/logs/clean")
async def clean_logs():
    return await get_logs_clean()

@app.get("/logs")
async def full_logs():
    return await get_logs_full()
