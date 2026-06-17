from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

from app.database.connection import engine
from app.models.Base import Base

# Менеджер контекста для асинхронного управления жизненным циклом приложения
from contextlib import asynccontextmanager

# Импорт класса логирования в middleware
from app.middleware.LoggingMiddleware import LoggingMiddleware

# Импорт роутеров
# Redis
from app.service.redis.redis_client import router_redis
# Catalog импорт по зависимости, от независимого к зависимому
from app.routers.router_assets_history import router_assets_history     # не зависим
from app.routers.router_users import router_users                       # не зависим (ссылка на департамент)
from app.routers.router_software import router_software                 # не зависим
# Catalog импорт по зависимости, от независимого к зависимому
from app.routers.router_catalog_history import router_catalog_history   # не зависим (чисто история)
from app.routers.router_assets_excel import router_assets_excel         # не зависим
from app.routers.router_locations import router_locations               # не зависим

from app.routers.router_assets_types import router_assets_types         # тип не зависим
from app.routers.router_catalog_classes import router_catalog_classes   # класс зависит от типа
from app.routers.router_catalog_models import router_catalog_models     # модель зависим от класса
from app.routers.router_assets import router_assets                     # зависим от: модели, warehouse, vendor, software, +(опционально) содержит ссылку на самого себя
from app.routers.router_catalog_items import router_catalog_items       # каталог зависим от модели, актива, пользователя (смысл = связать много активов с пользователями)

from app.routers.router_companies import router_companies               # зависим от локации
from app.routers.router_vendors import router_vendors                   # зависим от vendor_classes, компании
from app.routers.router_vendor_classes import router_vendor_classes     # не зависим
from app.routers.router_warehouses import router_warehouses             # зависим от локации
from app.routers.router_auth import router_auth                         # работает с redis и таблицей users


# Департамент -> Отдел -> Группа
from app.routers.router_departments import router_departments           # департамент зависит от отдела
from app.routers.router_divisions import router_divisions               # отдел зависит от группы
from app.routers.router_groups import router_groups                     # группа не зависима

# Роутер заполнения таблиц
from app.seed_api import router_seed_api                                # не зависим

# Роутеры для данных о ПК и андроид устройств
from app.routers.router_pc_data import router_pc_data
from app.routers.router_android_data import router_android_data

# Роутеры для карты активов
from app.routers.router_asset_position import router_asset_position
from app.routers.router_workshop import router_workshop


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажи конкретные домены
    allow_credentials=True,
    allow_methods=["*"],  # Разрешить все HTTP методы
    allow_headers=["*"],  # Разрешить все заголовки
)

app.add_middleware(LoggingMiddleware)

# --- Подключение API Маршрутов ---
# Карта активов
app.include_router(router_auth, prefix="/api")              # Auth
app.include_router(router_assets, prefix="/api")            # Assets
app.include_router(router_workshop, prefix="/api")
app.include_router(router_asset_position, prefix="/api")

# Redis
app.include_router(router_redis, prefix="/api")             # Only DEV: check redis storage

app.include_router(router_users, prefix="/api")             # Users

# app.include_router(router_seed_api, prefix="/api")        # Only DEV: seed api

app.include_router(router_departments, prefix="/api")       # Департамент
app.include_router(router_divisions, prefix="/api")         # Отдел
app.include_router(router_groups, prefix="/api")            # Группа

app.include_router(router_assets_types, prefix="/api")      # Asset Types
app.include_router(router_catalog_classes, prefix="/api")   # Catalog Classes
app.include_router(router_catalog_models, prefix="/api")    # Catalog Models
app.include_router(router_catalog_items, prefix="/api")     # Catalog Items

app.include_router(router_assets_history, prefix="/api")    # Assets History
app.include_router(router_catalog_history, prefix="/api")   # Catalog History

app.include_router(router_software, prefix="/api")          # Software
app.include_router(router_vendor_classes, prefix="/api")    # Vendor Classes
app.include_router(router_vendors, prefix="/api")           # Vendors
app.include_router(router_warehouses, prefix="/api")        # Warehouse
app.include_router(router_companies, prefix="/api")         # Companies

app.include_router(router_locations, prefix="/api")         # Location

app.include_router(router_assets_excel, prefix="/api")      # Excel

app.include_router(router_pc_data, prefix="/api")           # PC DATA
app.include_router(router_android_data, prefix="/api")      # Android DATA


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