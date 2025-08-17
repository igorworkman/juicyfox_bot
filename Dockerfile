FROM python:3.11-slim-buster
WORKDIR /app

# Устанавливаем системные зависимости (для aiohttp, uvicorn, psycopg2, aiosqlite и т.д.)
RUN apt-get update && apt-get install -y \
    curl \
    bash \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Создание папки с правами
RUN mkdir -p /app/data && chmod 777 /app/data

# Копируем весь проект
COPY . .

EXPOSE 8000
CMD ["gunicorn", "api.main:app", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
VOLUME /data
