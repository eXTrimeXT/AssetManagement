FROM python:3.14.3-slim
WORKDIR /app

# Устанавливаем системные зависимости (для psycopg2 или других библиотек, если понадобятся)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY packages /packages
COPY requirements.txt .

COPY packages/Booktype-1.5-py2.7.egg /tmp/
RUN pip install --no-cache-dir /tmp/Booktype-1.5-py2.7.egg

# Если не доступен Docker на сервере
#RUN pip install --no-cache-dir --no-index --find-links=/packages -r requirements.txt

# Если локальная сборка образа имеет доступ к pypi.org
RUN pip install -r requirements.txt

# Копируем код приложения
COPY . .

# Копируем скрипт запуска
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Запуск через скрипт-обёртку
CMD ["/bin/bash", "entrypoint.sh"]