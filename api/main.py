from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from aiogram.types import Update
from juicyfox_bot_single import main as run_bot, dp, bot_pool
from .check_logs import get_logs_clean, get_logs_full

app = FastAPI(default_response_class=JSONResponse)

@app.get("/logs")
async def full_logs():
    return await get_logs_full()

@app.get("/logs/clean")
async def clean_logs():
    return await get_logs_clean()

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
