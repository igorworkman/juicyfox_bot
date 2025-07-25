import os
import httpx
from dotenv import load_dotenv
import aiofiles

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
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}?tailLines=20", headers=HEADERS)
            response.raise_for_status()
            data = response.json()
            logs = [entry.get("log", "") for entry in data.get("logs", [])]
            return {"logs": logs}
    except httpx.HTTPStatusError as e:
        return {
            "error": f"HTTP ошибка Northflank: {e.response.status_code}",
            "detail": e.response.text
        }
    except Exception as e:
        return {
            "error": "Ошибка при получении логов",
            "detail": str(e)
        }

async def get_logs_full():
    try:
        async with aiofiles.open("logs/runtime.log", mode="r") as f:
            content = await f.read()
        lines = content.strip().splitlines()[-50:]
        return {"lines": lines}
    except Exception as e:
        return {"error": str(e)}

