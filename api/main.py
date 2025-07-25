from fastapi import FastAPI
from check_logs import get_logs_clean, get_logs_full

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "FastAPI работает! 🎉"}

@app.get("/logs/clean")
async def clean_logs():
    return await get_logs_clean()

@app.get("/logs")
async def full_logs():
    return await get_logs_full()
