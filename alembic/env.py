import asyncio
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Импортируем твои модели и настройки БД
# Важно: импортируй Base и все модели, чтобы Alembic их видел!

# Импорт всех моделей, чтобы они зарегистрировались в метаданных Base
from app.models.Base import Base
from app.database.connection import DB_URL # переменная с URL из connection.py

# ВАЖНО: Импортируйте ВСЕ модели здесь, чтобы они зарегистрировались в Base.metadata
from app.models import Asset, User, Location, Software, Warehouse, AssetType, AssetCatalog, AssetClass, AssetModel
# Добавьте новые модели:
from app.models.Vendor import Vendor
from app.models.Company import Company
from app.models.VendorClass import VendorClass

# ... rest of the file ...
target_metadata = Base.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = DB_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # Используем синхронный движок для offline режима или тестов, 
    # но для асинхронного проекта лучше использовать async_engine_from_config
    # Однако Alembic требует синхронное соединение для apply_migrations в некоторых случаях,
    # поэтому стандартный паттерн для asyncpg в Alembic выглядит так:

    connectable = async_engine_from_config(
        {"sqlalchemy.url": DB_URL},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()