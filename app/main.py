import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# подключение бд и модели
from app.database.connection import engine
from app.models.Base import Base

# Менеджер контекста для асинхронного управления жизненным циклом приложения
from contextlib import asynccontextmanager

# Импорт класса логирования в middleware
from app.middleware.LoggingMiddleware import LoggingMiddleware


# Импорт роутеров
from app.routers.router_assets import router_assets
from app.routers.router_assets_types import router_assets_types
from app.routers.router_users import router_users
from app.routers.router_software import router_software
from app.routers.router_locations import router_locations
from app.routers.router_catalog import router_catalog
from app.routers.router_warehouses import router_warehouses
from app.routers.router_companies import router_companies
from app.routers.router_vendor_classes import router_vendor_classes
from app.routers.router_vendors import router_vendors
from app.routers.router_assets_excel import router_assets_excel


# Импорт роутеров Excel


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
    version="1.0.0"
)

# --- Подключение MiddleWare ---
app.add_middleware(LoggingMiddleware)

# --- Подключение API Маршрутов ---
app.include_router(router_assets, prefix="/api")
app.include_router(router_assets_types, prefix="/api")
app.include_router(router_users, prefix="/api")
app.include_router(router_software, prefix="/api")
app.include_router(router_locations, prefix="/api")
app.include_router(router_catalog, prefix="/api")
app.include_router(router_warehouses, prefix="/api")

# Vendors
app.include_router(router_vendors, prefix="/api")
app.include_router(router_vendor_classes, prefix="/api")

# Companies
app.include_router(router_companies, prefix="/api")

# Excel
# app.include_router(router_catalog_excel, prefix="/api")
app.include_router(router_assets_excel, prefix="/api")
