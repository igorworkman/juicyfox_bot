FROM python:3.11-slim-buster
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    curl \
    bash \
    build-essential \
    gcc \
    git \
    libffi-dev \
    libssl-dev \
    libsqlite3-dev \
    libpq-dev \
    zlib1g-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем зависимости Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Создаём папку для данных
RUN mkdir -p /app/data && chmod 777 /app/data

# Копируем весь проект
COPY . .

EXPOSE 8000
CMD ["gunicorn", "api.main:app", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
VOLUME /data
