import os
from typing import AsyncGenerator, Any
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

"""
База данных (Async + Pooling)
Получаем строку подключения из переменных окружения. 
Если переменной нет, используется значение по умолчанию для локального запуска.
Формат: postgresql+asyncpg://<user>:<password>@<host>:<port>/<dbname>
"""
DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/it_assets_db2")

"""
Создаем асинхронный движок SQLAlchemy.
pool_size=10: Количество постоянных соединений в пуле (держит 10 соединений открытыми).
max_overflow=20: Максимальное количество дополнительных соединений сверх pool_size при пиковой нагрузке.
pool_pre_ping=True: Перед использованием соединения отправляет простой запрос, чтобы убедиться, 
что соединение с БД не разорвано. Критично для стабильности.
"""
engine = create_async_engine(DB_URL, pool_size=10, max_overflow=20, pool_pre_ping=True)

"""
Фабрика асинхронных сессий.
expire_on_commit=False: После commit() объекты не становятся "detached" (не теряют доступ к атрибутам).
Это важно для async, чтобы избежать ошибок при обращении к полям объекта после закрытия транзакции.
"""
async_session = async_sessionmaker(engine, expire_on_commit=False)

"""
Зависимость FastAPI для получения сессии БД в эндпоинтах.
AsyncGenerator[AsyncSession, Any]: Подсказка типа для генератора.
"""
async def get_db() -> AsyncGenerator[AsyncSession, Any]:
    # Создаем новую сессию из фабрики.
    async with async_session() as session:
        try:
            # Возвращаем сессию в эндпоинт.
            # Код эндпоина выполняется здесь.
            yield session
        finally:
            # Гарантированно закрываем сессию после завершения запроса (даже если была ошибка),
            # возвращая соединение обратно в пул.
            pass
            # Примечание: async with сам закроет сессию при выходе из блока,
            # но явная структура try/finally часто добавляется для логирования ошибок или отката транзакций.