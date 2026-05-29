#!/bin/bash
echo "entrypoint.sh: Запуск контейнера приложения..."

# 1. Ожидание готовности PostgreSQL
echo "entrypoint.sh: Ожидание доступности базы данных..."
until python -c "import asyncio; from app.database.connection import engine; asyncio.run(engine.connect())" 2> /dev/null
do
    echo "entrypoint.sh: База данных пока не готова, повторяю через 2 секунды..."
    sleep 2
done
echo "entrypoint.sh: База данных подключена!"

# 2. Применение миграций Alembic
#echo "Применение миграций Alembic..."
#alembic upgrade head

# 3. Запуск основного сервера FastAPI
echo "entrypoint.sh: Запуск FastAPI сервера..."
# Уровни логирования: critical, error, warning, info, debug, trace.
exec uvicorn app.main:app --host 0.0.0.0 --port 8800 --reload --log-level info
