import os
import httpx
from dotenv import load_dotenv

load_dotenv()

NORTHFLANK_API_TOKEN = os.getenv("NORTHFLANK_API_TOKEN")
NORTHFLANK_PROJECT_ID = os.getenv("NORTHFLANK_PROJECT_ID")
NORTHFLANK_SERVICE_ID = os.getenv("NORTHFLANK_SERVICE_ID")

HEADERS = {"Authorization": f"Bearer {NORTHFLANK_API_TOKEN}"}

BASE_URL = (
    f"https://api.northflank.com/v1/projects/"
    f"{NORTHFLANK_PROJECT_ID}/services/{NORTHFLANK_SERVICE_ID}/logs"
)

async def get_logs_clean():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}?tailLines=20", headers=HEADERS)
        if response.status_code != 200:
            return {
                "error": f"Ошибка Northflank: {response.status_code}",
                "detail": response.text
            }
        data = response.json()
        logs = [entry.get("log", "") for entry in data.get("logs", [])]
        return {"logs": logs}

async def get_logs_full():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}?tailLines=200", headers=HEADERS)
        if response.status_code != 200:
            return {
                "error": f"Ошибка Northflank: {response.status_code}",
                "detail": response.text
            }
        return response.json()
