FROM python:3.11-slim-buster
WORKDIR /app

# Установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Установка curl и bash (для дебага)
RUN apt-get update && apt-get install -y curl bash && rm -rf /var/lib/apt/lists/*

# Создание папки с правами
RUN mkdir -p /app/data && chmod 777 /app/data

# Копируем весь проект
COPY . .

EXPOSE 8000
CMD ["gunicorn", "api.main:app", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
VOLUME /data
