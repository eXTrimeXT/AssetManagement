"""
Скрипт для начального заполнения таблицы asset_types.
Запуск: python seed_asset_types.py
"""
import asyncio
from sqlalchemy import select

# Импортируем настройки подключения
from app.database.connection import engine, async_session

# Импортируем БАЗУ — обязательно первой
from app.models.Base import Base

# Импортируем ВСЕ модели, чтобы SQLAlchemy увидел все связи
# Это критично для отношений с back_populates и строковыми ссылками
from app.models.AssetType import AssetType
from app.models.Asset import Asset
from app.models.User import User
from app.models.UserAsset import UserAsset
from app.models.Software import Software

# После импорта всех моделей — явно конфигурируем мапперы
from sqlalchemy.orm import configure_mappers
configure_mappers()  # Принудительная конфигурация всех отношений

# Константа со списком типов для заполнения
ASSET_TYPES_SEED = [
    ("Компьютер", 10),
    ("Серверное", 20),
    ("Сетевое", 30),
    ("Расходники", 40),
    ("MES", 50),
]


async def seed_asset_types():
    """Асинхронная функция для выполнения посева данных."""
    try:
        # 1. Инициализация структуры БД
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # 2. Работа с данными
        async with async_session() as session:
            for name, type_id in ASSET_TYPES_SEED:
                result = await session.execute(
                    select(AssetType).where(AssetType.type_id == type_id)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    if existing.name != name:
                        existing.name = name
                        print(f"Обновлено: type_id={type_id} | {existing.name}")
                else:
                    new_type = AssetType(name=name, type_id=type_id)
                    session.add(new_type)
                    print(f"Добавлено: {name} (type_id={type_id})")

            await session.commit()
            print("\nSeed завершён успешно!")

    except Exception as e:
        print(f"Ошибка: {type(e).__name__}: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_asset_types())