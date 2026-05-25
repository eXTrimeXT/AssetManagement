from fastapi import FastAPI, Depends

from app.database.connection import engine
from app.models.Base import Base

# Менеджер контекста для асинхронного управления жизненным циклом приложения
from contextlib import asynccontextmanager

# Импорт класса логирования в middleware
from app.middleware.LoggingMiddleware import LoggingMiddleware

# Импорт роутеров
from app.routers.router_assets import router_assets
from app.routers.router_assets_history import router_assets_history
from app.routers.router_users import router_users                       # не зависим
from app.routers.router_software import router_software
# Catalog импорт по зависимости, от независимого к зависимому
from app.routers.router_catalog_history import router_catalog_history   # не зависим (чисто история)
from app.routers.router_assets_types import router_assets_types         # не зависим
from app.routers.router_catalog_classes import router_catalog_classes   # зависит от типа
from app.routers.router_catalog_models import router_catalog_models     # зависим от класса
from app.routers.router_catalog_items import router_catalog_items       # зависим от модели
from app.routers.router_companies import router_companies
from app.routers.router_vendors import router_vendors
from app.routers.router_vendor_classes import router_vendor_classes
from app.routers.router_warehouses import router_warehouses
from app.routers.router_locations import router_locations
from app.routers.router_auth import router_auth
from app.routers.router_assets_excel import router_assets_excel
# Департамент -> Отдел -> Группа
from app.routers.router_departments import router_departments
from app.routers.router_divisions import router_divisions
from app.routers.router_groups import router_groups

from app.seed_api import router_seed_api


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

    # Для разработки раскомментировать
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

# --- Создание экземпляра приложения ---
app = FastAPI(
    lifespan=lifespan,
    title="IT Assets API",
    description="API для управления IT-активами компании",
    version="1.0.0",
)

# --- Подключение MiddleWare ---
app.add_middleware(LoggingMiddleware)

# --- Подключение API Маршрутов ---
# Redis
from app.service.redis.redis_client import *
app.include_router(router_redis, prefix="/api")
app.include_router(router_auth, prefix="/api")              # Auth
app.include_router(router_users, prefix="/api")             # Users

# app.include_router(router_seed_api, prefix="/api")          # Only DEV: seed api

app.include_router(router_departments)
app.include_router(router_divisions)
app.include_router(router_groups)

app.include_router(router_assets_types, prefix="/api")      # Asset Types
app.include_router(router_catalog_classes, prefix="/api")   # Catalog Classes
app.include_router(router_catalog_models, prefix="/api")    # Catalog Models
app.include_router(router_assets, prefix="/api")            # Assets
app.include_router(router_catalog_items, prefix="/api")     # Catalog Items
app.include_router(router_assets_history, prefix="/api")    # Assets History
app.include_router(router_catalog_history, prefix="/api")   # Catalog History
app.include_router(router_software, prefix="/api")          # Software
app.include_router(router_companies, prefix="/api")         # Companies
app.include_router(router_warehouses, prefix="/api")        # Warehouse
app.include_router(router_vendors, prefix="/api")           # Vendors
app.include_router(router_vendor_classes, prefix="/api")    # Vendor Classes
app.include_router(router_locations, prefix="/api")         # Location
app.include_router(router_assets_excel, prefix="/api")      # Excel

