from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

from app.database.connection import engine
from app.models.Base import Base

# Менеджер контекста для асинхронного управления жизненным циклом приложения
from contextlib import asynccontextmanager

# Middleware's
# Импорт класса логирования в middleware
from app.middleware.LoggingMiddleware import LoggingMiddleware
# Middleware для автоматической авторизации
# from app.middleware.AuthTokenMiddleware import AuthTokenMiddleware

# Импорт роутеров
# Redis
from app.services.redis.redis_client import router_redis

# Роутеры для данных о ПК и андроид устройств
from app.routers.router_pc_data import router_pc_data
from app.routers.router_android_data import router_android_data

from app.routers.router_zup import router_zup                           # Интеграция с 1С
from app.routers.router_auth import router_auth                         # Роутер авторизации пользователей


from app.routers.router_locations import router_locations               # не зависим
from app.routers.router_companies import router_companies               # зависим от локации
from app.routers.router_vendor_classes import router_vendor_classes     # не зависим
from app.routers.router_vendors import router_vendors                   # зависим от vendor_classes, компании

# from app.routers.router_assets_types import router_assets_types         # тип не зависим
# from app.routers.router_catalog_classes import router_catalog_classes   # класс зависит от типа
# from app.routers.router_catalog_models import router_catalog_models     # модель зависим от класса
# from app.routers.router_assets import router_assets                     # зависим от: модели, warehouse, vendor, software, +(опционально) содержит ссылку на самого себя
# from app.routers.router_catalog_items import router_catalog_items       # каталог зависим от модели, актива, пользователя (смысл = связать много активов с пользователями)

from app.routers.assets import (
    router_asset_types,
    router_asset_classes,
    router_asset_models,
    router_assets,
    router_asset_assignments
)


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

    # Инициализация дефолтного конфига карты
    # await MapConfigService.init_default_config()

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажи конкретные домены
    allow_credentials=True,
    allow_methods=["*"],  # Разрешить все HTTP методы
    allow_headers=["*"],  # Разрешить все заголовки
)

app.add_middleware(LoggingMiddleware)
# app.add_middleware(AuthTokenMiddleware)

# --- Подключение API Маршрутов ---
app.include_router(router_redis, prefix="/api")             # Only DEV: check redis storage
app.include_router(router_auth, prefix="/api")              # Роутер авторизации
app.include_router(router_pc_data, prefix="/api")           # PC DATA
app.include_router(router_android_data, prefix="/api")      # Android DATA
app.include_router(router_zup, prefix="/api")               # 1С ЗУП

app.include_router(router_locations, prefix="/api")         # Location
app.include_router(router_companies, prefix="/api")         # Companies
app.include_router(router_vendor_classes, prefix="/api")    # Vendor Classes
app.include_router(router_vendors, prefix="/api")           # Vendors

app.include_router(router_asset_types, prefix="/api")
app.include_router(router_asset_classes, prefix="/api")
app.include_router(router_asset_models, prefix="/api")
app.include_router(router_assets, prefix="/api")
app.include_router(router_asset_assignments, prefix="/api")


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