FROM python:3.14.3-slim

WORKDIR /app

# Устанавливаем системные зависимости (для psycopg2 или других библиотек, если понадобятся)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY packages /packages
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/packages -r requirements.txt

# Копируем код приложения
COPY . .

# Копируем скрипт запуска
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Запуск через скрипт-обёртку
CMD ["/bin/bash", "entrypoint.sh"]