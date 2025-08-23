# api/check_logs.py
from fastapi import APIRouter
import os

# Используем переменную окружения LOG_FILE_PATH или путь по умолчанию
def _log_file_path() -> str:
    return os.getenv("LOG_FILE_PATH", "/app/logs/bot.log")

router = APIRouter()

@router.get("/logs")
async def get_logs():
    """
    Возвращает последние 100 строк из лог-файла.
    Если файл не найден, возвращает пустой список.
    """
    path = _log_file_path()
    if not os.path.exists(path):
        return {"logs": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()[-100:]
    except Exception as exc:
        return {"error": f"Cannot read log file: {exc}"}
    return {"logs": lines}

@router.post("/logs/clean")
async def clean_logs():
    """
    Очищает лог-файл (обрезает содержимое).
    """
    path = _log_file_path()
    try:
        with open(path, "w", encoding="utf-8"):
            pass
    except Exception as exc:
        return {"error": f"Cannot clean log file: {exc}"}
    return {"status": "cleaned"}
Здесь путь к файлу можно переопределить через LOG_FILE_PATH, но по умолчанию используется /app/logs/bot.log, как в Docker‑образах.
api/main.py нужно поправить импорт лог‑роутера. Сейчас файл делает from api.check_logs import logs_router, но в новом варианте роутер называется просто router. Импорт можно унифицировать, как у остальных роутеров:
# api/main.py
from fastapi import FastAPI

from api.webhook import router as webhook_router
from api.payments import router as payments_router
from api.health import router as health_router
from api.check_logs import router as logs_router  # обновленный импорт

app = FastAPI(title="JuicyFox API", version="1.0.0")

app.include_router(webhook_router,  prefix="/bot")
app.include_router(payments_router, prefix="/payments")
app.include_router(health_router)
app.include_router(logs_router)
