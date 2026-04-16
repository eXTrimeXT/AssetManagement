#!/bin/bash
echo "Запуск контейнера приложения..."

# 1. Ожидание готовности PostgreSQL
echo "Ожидание доступности базы данных..."
until python -c "import asyncio; from app.database.connection import engine; asyncio.run(engine.connect())" 2> /dev/null
do
    echo "База данных пока не готова, повторяю через 2 секунды..."
    sleep 2
done
echo "База данных подключена!"

# 2. Применение миграций Alembic
#echo "Применение миграций Alembic..."
#alembic upgrade head

# 3. Запуск основного сервера FastAPI
echo "Запуск FastAPI сервера..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8800 --reload