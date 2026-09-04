import asyncio
import json
import logging
import os

import asyncpg
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

from app.database.connection import engine
from app.models.Base import Base

# Менеджер контекста для асинхронного управления жизненным циклом приложения
from contextlib import asynccontextmanager

# Middleware's
# Импорт класса логирования в middleware
from app.middleware.LoggingMiddleware import LoggingMiddleware
# Middleware для проверки авторизации
from app.middleware.AuthTokenMiddleware import AuthTokenMiddleware

# Импорт менеджера уведомлений
from app.services.notifications import notification_manager

# Импорт роутеров
# Роутеры для данных о ПК и андроид устройств
from app.routers.router_pc_data import router_pc_data
from app.routers.router_android_data import router_android_data

from app.routers.router_zup import router_zup                           # Интеграция с 1С
from app.routers.router_auth import router_auth                         # Роутер авторизации пользователей

from app.routers.router_locations import router_locations               # не зависим
from app.routers.router_companies import router_companies               # зависим от локации
from app.routers.router_vendor_classes import router_vendor_classes     # не зависим
from app.routers.router_vendors import router_vendors                   # зависим от vendor_classes, компании

from app.routers.assets import (
    router_asset_status,        # Статусы не зависимы
    router_asset_types,         # Тип не зависим
    router_asset_models,        # Модель зависим от класса
    router_assets,              # Зависим от: модели, warehouse, vendor, software, +(опционально) содержит ссылку на самого себя
    router_asset_assignments,   # Каталог зависим от модели, актива, пользователя (смысл = связать много активов с пользователями)
    router_asset_history,       # История актива
    router_asset_write_off,     # Списание актива
)

# Роутер инвентаризации
from app.routers.router_inventorization import router_inventorization

# Импорт роутеров карты цехов и позиций активов
from app.routers.map_assets.router_workshop import router_workshop
from app.routers.map_assets.router_asset_positions import router_asset_positions
from app.routers.map_assets.router_map import router_map

# Импорт роутера аудита
from app.routers.router_audit import router_audit

# Аналитика
from app.routers.router_analytics import router_analytics

# Планировщик задач
from app.scheduler.scheduler import init_scheduler, shutdown_scheduler

# Импорт роутера уведомлений
from app.routers.router_notifications import router_notifications
from app.services.zup.zup_integration import close_http_client

logger = logging.getLogger(__name__)

# --- Управление жизненным циклом (Lifespan) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Функция, выполняемая при запуске и завершении работы приложения.

    STARTUP:
    1. engine.begin() открывает транзакцию с БД.
    2. conn.run_sync(Base.metadata.create_all) синхронно создает все таблицы,
       описанные в моделях (классы, наследующие Base), если они еще не существуют в БД.
    """

    # Запуск слушателя БД для уведомлений
    listener_task = asyncio.create_task(db_notification_listener())

    # При старте приложения
    init_scheduler()


    # Для разработки раскомментировать
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)

    yield # Завершение жизненного цикла приложения

    # Остановка при завершении работы приложения
    listener_task.cancel()

    # Завершаем выполенение планировщика задач
    shutdown_scheduler()
    await close_http_client()

async def db_notification_listener():
    try:
        # 1. Берем URL из переменных окружения
        db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/it_assets_db")

        # 2. Убираем префикс "+asyncpg", так как чистый asyncpg его не понимает
        clean_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

        # 3. Создаем ПРЯМОЕ соединение asyncpg
        conn = await asyncpg.connect(clean_url)

        # 4. Функция обратного вызова, которая сработает при получении уведомления
        async def notification_callback(connection, pid, channel, payload):
            logger.debug(f"ПОЛУЧЕНО ИЗ БД: канал={channel}, payload={payload}")
            try:
                parsed_payload = json.loads(payload)
                await notification_manager.broadcast(parsed_payload)
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON из БД: {e}")

        # 5. Подписываемся на канал через add_listener, как вы и просили
        await conn.add_listener("notification_channel", notification_callback)
        logger.info("Слушатель уведомлений БД успешно запущен через add_listener.")

        # 6. Держим задачу живой, пока работает приложение
        stop_event = asyncio.Event()
        try:
            await stop_event.wait()
        except asyncio.CancelledError:
            # При завершении приложения корректно отписываемся и закрываем соединение
            logger.info("Остановка слушателя уведомлений БД...")
            await conn.remove_listener("notification_channel", notification_callback)
            await conn.close()
            raise

    except Exception as e:
        logger.error(f"Критическая ошибка при запуске слушателя БД: {e}")
        import traceback
        traceback.print_exc()

# --- Создание экземпляра приложения ---
app = FastAPI(
    lifespan=lifespan,
    title="IT Assets API",
    description="API для управления IT-активами компании",
    version="1.0.0",
)

# --- Подключение MiddleWare ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажи конкретные домены
    allow_credentials=True,
    allow_methods=["*"],  # Разрешить все HTTP методы
    allow_headers=["*"],  # Разрешить все заголовки
)

app.add_middleware(LoggingMiddleware)
app.add_middleware(AuthTokenMiddleware)

# --- Подключение API Маршрутов ---
app.include_router(router_auth, prefix="/api")              # Роутер авторизации
app.include_router(router_pc_data, prefix="/api")           # PC DATA
app.include_router(router_android_data, prefix="/api")      # Android DATA
app.include_router(router_zup, prefix="/api")               # 1С ЗУП

app.include_router(router_audit, prefix="/api")

app.include_router(router_locations, prefix="/api")         # Location
app.include_router(router_companies, prefix="/api")         # Companies
app.include_router(router_vendor_classes, prefix="/api")    # Vendor Classes
app.include_router(router_vendors, prefix="/api")           # Vendors

app.include_router(router_asset_status, prefix="/api")      # Asset Types
app.include_router(router_asset_types, prefix="/api")       # Asset Types
app.include_router(router_asset_models, prefix="/api")      # Asset Models
app.include_router(router_asset_assignments, prefix="/api") # Asset Assignment
app.include_router(router_assets, prefix="/api")            # Assets
app.include_router(router_asset_positions, prefix="/api")   # Роутер позиций активов
app.include_router(router_asset_history, prefix="/api")     # История активов
app.include_router(router_asset_write_off, prefix="/api")   # Списание активов

app.include_router(router_inventorization, prefix="/api")   # Инвентаризация активов

app.include_router(router_analytics, prefix="/api")         # Аналитика

# Карта активов
app.include_router(router_workshop, prefix="/api")          # Схема цехов для карты
app.include_router(router_map, prefix="/api")               # Роутер html-карты

# Уведомления
app.include_router(router_notifications, prefix="/api")     # Роутер уведомлений


router_root = APIRouter(tags=["/"])
@router_root.get("/")
async def root():
    host = "localhost"
    port = "8800"
    return {
        "docs": f"http://{host}:{port}/docs",
        "api": f"http://{host}:{port}/api"
    }

app.include_router(router_root)                             # корень веб-приложения