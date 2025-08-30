# ---------- deps (build stage) ----------
FROM python:3.11-slim-bookworm AS deps
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# системные заголовки только на этапе сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc curl git \
    libffi-dev libssl-dev zlib1g-dev \
  && rm -rf /var/lib/apt/lists/*

# зависимости ставим в отдельный префикс, чтобы потом скопировать только его
COPY requirements.txt .
RUN python -m pip install --upgrade pip \
 && python -m pip install --prefix=/install -r requirements.txt

# ---------- runtime ----------
FROM python:3.11-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=prod \
    TZ=UTC \
    PORT=8080
WORKDIR /app

# создаём не-root пользователя
RUN useradd -m -u 10001 appuser

# переносим только установленное из deps
COPY --from=deps /install /usr/local

# код приложения
COPY . /app

# директории для данных/логов
RUN mkdir -p /app/data /app/logs \
 && chown -R appuser:appuser /app
USER appuser

# порт API (uvicorn) — теперь 8080
EXPOSE 8080


# Для запуска FastAPI через Uvicorn
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]

