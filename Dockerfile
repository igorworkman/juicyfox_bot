FROM python:3.10-slim-buster

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем только нужные файлы
COPY juicyfox_bot_single.py .
COPY locales ./locales
COPY static ./static

# Запуск бота
EXPOSE 8080
CMD ["python", "juicyfox_bot_single.py"]
VOLUME /data
