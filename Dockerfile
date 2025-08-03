FROM python:3.11-slim-buster
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 👇 Вот эта строка — создаёт и даёт права на папку!
RUN mkdir -p /app/data && chmod 777 /app/data

COPY . .

EXPOSE 8000
CMD ["gunicorn", "api.main:app", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
VOLUME /data
