from fastapi import APIRouter
import os

logs_router = APIRouter()

@logs_router.get("/logs")
async def get_logs():
    path = "/app/logs/bot.log"
    if not os.path.exists(path):
        return {"logs": ""}
    with open(path, "r") as f:
        return {"logs": f.read().splitlines()[-100:]}

@logs_router.post("/logs/clean")
async def clean_logs():
    path = "/app/logs/bot.log"
    open(path, "w").close()
    return {"status": "cleaned"}
