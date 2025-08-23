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
