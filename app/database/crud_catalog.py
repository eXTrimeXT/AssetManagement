from datetime import datetime
from typing import List, Optional, Sequence, Any, Dict
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd
from sqlalchemy.orm import selectinload

from app.models.AssetClass import AssetClass
from app.models.AssetModel import AssetModel
from app.models.AssetCatalog import AssetCatalog
from app.models.Asset import Asset

from app.schemas.catalog.ClassSchemas import AssetClassCreate, AssetClassUpdate
from app.schemas.catalog.ModelSchemas import AssetModelCreate, AssetModelUpdate
from app.schemas.catalog.CatalogSchemas import AssetCatalogCreate
from app.models.Warehouse import Warehouse
from app.models.Company import Company
from app.models.Vendor import Vendor


# === CLASS CRUD ===
async def create_asset_class(db: AsyncSession, data: AssetClassCreate) -> AssetClass:
    db_obj = AssetClass(**data.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    # Подгружаем связи для возврата полного объекта сразу после создания
    await db.refresh(db_obj, attribute_names=["asset_type", "creator", "updater"])
    return db_obj

async def get_asset_class_by_id(db: AsyncSession, class_id: int) -> Optional[AssetClass]:
    """Получает класс по ID со всеми связями"""
    result = await db.execute(
        select(AssetClass)
        .where(AssetClass.class_id == class_id)
        .options(
            selectinload(AssetClass.asset_type),
            selectinload(AssetClass.creator),
            selectinload(AssetClass.updater)
        )
    )
    return result.scalar_one_or_none()

async def get_asset_classes(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[Any]:
    """Получает список классов со связями"""
    query = select(AssetClass).options(
        selectinload(AssetClass.asset_type),
        selectinload(AssetClass.creator),
        selectinload(AssetClass.updater)
    ).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

async def update_asset_class(db: AsyncSession, class_id: int, data: AssetClassUpdate) -> Optional[AssetClass]:
    obj = await get_asset_class_by_id(db, class_id) # Используем функцию с load
    if not obj:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(obj, k, v)

    obj.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(obj)
    # После обновления связи могут сброситься, подгружаем снова
    await db.refresh(obj, attribute_names=["asset_type", "creator", "updater"])
    return obj

async def delete_asset_class(db: AsyncSession, class_id: int) -> bool:
    obj = await db.get(AssetClass, class_id)
    if not obj: return False
    await db.delete(obj)
    await db.commit()
    return True


# === MODEL CRUD ===
async def create_asset_model(db: AsyncSession, data: AssetModelCreate) -> AssetModel:
    db_obj = AssetModel(**data.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    # Подгружаем связи для возврата полного объекта
    await db.refresh(db_obj, attribute_names=["asset_class", "creator", "updater"])
    return db_obj

async def get_asset_model_by_id(db: AsyncSession, model_id: int) -> Optional[AssetModel]:
    """Получает модель по ID со всеми глубокими связями"""
    result = await db.execute(
        select(AssetModel)
        .where(AssetModel.model_id == model_id)
        .options(
            # Загружаем класс
            selectinload(AssetModel.asset_class)
            .options(
                # Внутри класса загружаем его тип и пользователей
                selectinload(AssetClass.asset_type),
                selectinload(AssetClass.creator),
                selectinload(AssetClass.updater)
            ),
            # Загружаем пользователей самой модели
            selectinload(AssetModel.creator),
            selectinload(AssetModel.updater)
        )
    )
    return result.scalar_one_or_none()

async def get_asset_models(
        db: AsyncSession,
        class_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50
) -> Sequence[Any]:
    """Получает список моделей со всеми глубокими связями"""
    query = select(AssetModel).options(
        selectinload(AssetModel.asset_class)
        .options(
            selectinload(AssetClass.asset_type),
            selectinload(AssetClass.creator),
            selectinload(AssetClass.updater)
        ),
        selectinload(AssetModel.creator),
        selectinload(AssetModel.updater)
    )

    if class_id:
        query = query.where(AssetModel.class_id == class_id)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

async def update_asset_model(db: AsyncSession, model_id: int, data: AssetModelUpdate) -> Optional[AssetModel]:
    obj = await get_asset_model_by_id(db, model_id) # Используем функцию с load
    if not obj:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(obj, k, v)

    obj.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(obj)
    # После обновления связи могут сброситься, подгружаем снова
    # Примечание: refresh с attribute_names может не подгрузить вложенные опции selectinload,
    # поэтому для гарантированного результата лучше сделать отдельный запрос или использовать joinedload в модели.
    # Но так как у нас selectinload в запросе получения, после commit() данные должны быть доступны,
    # если сессия еще открыта. Для безопасности можно вызвать get_asset_model_by_id еще раз, но это лишний запрос.
    # В данном случае, так как мы используем async_sessionmaker с expire_on_commit=False (в connection.py),
    # объекты остаются прикрепленными. Однако, selectinload работает только при выполнении запроса.
    # Чтобы получить свежие данные связей после обновления, проще всего сделать новый запрос:
    return await get_asset_model_by_id(db, model_id)


# === CATALOG & STATISTICS CRUD ===
async def add_to_catalog(db: AsyncSession, data: AssetCatalogCreate) -> AssetCatalog:
    # Проверка: существует ли актив
    asset = await db.get(Asset, data.asset_id)
    if not asset:
        raise ValueError("Asset not found")

    db_obj = AssetCatalog(**data.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_catalog_stats_by_model(db: AsyncSession, model_id: int) -> dict:
    """
    Динамический подсчет количества активов для конкретной модели.
    Возвращает: {total: int, in_stock: int, in_use: int, repair: int}
    """
    # Базовый запрос: считаем активы, связанные с этой моделью через таблицу catalog
    # JOIN asset_catalog ac ON ac.model_id = :model_id
    # JOIN assets a ON a.asset_id = ac.asset_id

    subquery = select(AssetCatalog.asset_id).where(AssetCatalog.model_id == model_id)

    total_q = select(func.count()).select_from(Asset).where(Asset.asset_id.in_(subquery))

    # Статусы предполагаются строковыми, как в вашей модели (Приемка, На складе, Выдан...)
    # Адаптируйте строки статусов под ваши реальные значения в Enum или строках
    in_stock_q = select(func.count()).select_from(Asset).where(
        Asset.asset_id.in_(subquery),
        Asset.asset_status == 'WAREHOUSE' # Или 'На складе'
    )
    in_use_q = select(func.count()).select_from(Asset).where(
        Asset.asset_id.in_(subquery),
        Asset.asset_status == 'IN_USE' # Или 'Выдан'
    )

    total = await db.scalar(total_q) or 0
    in_stock = await db.scalar(in_stock_q) or 0
    in_use = await db.scalar(in_use_q) or 0

    return {
        "model_id": model_id,
        "total_count": total,
        "in_stock": in_stock,
        "in_use": in_use,
        "other": total - in_stock - in_use
    }

async def get_catalog_list(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[Any]:
    """
    Получает список записей каталога со ВСЕМИ глубокими связями.
    """
    query = select(AssetCatalog).options(
        # 1. Подгружаем Актив (asset)
        selectinload(AssetCatalog.asset).options(
            selectinload(Asset.asset_type),
            selectinload(Asset.location_obj),
            selectinload(Asset.preparer),      # prepared_by user
            selectinload(Asset.checker),       # checked_by user
            selectinload(Asset.software),
            selectinload(Asset.manufacturer).options( # Manufacturer is a Vendor
                selectinload(Vendor.vendor_class),
                selectinload(Vendor.company).options(
                    selectinload(Company.location_obj)
                ),
                selectinload(Vendor.creator)
            ),
            selectinload(Asset.vendor).options(     # Vendor is a Vendor
                selectinload(Vendor.vendor_class),
                selectinload(Vendor.company).options(
                    selectinload(Company.location_obj)
                ),
                selectinload(Vendor.creator)
            )
        ),

        # 2. Подгружаем Модель (model)
        selectinload(AssetCatalog.model).options(
            selectinload(AssetModel.asset_class).options(
                selectinload(AssetClass.asset_type),
                selectinload(AssetClass.creator),
                selectinload(AssetClass.updater)
            ),
            selectinload(AssetModel.creator),
            selectinload(AssetModel.updater)
        ),

        # 3. Подгружаем Владельца (owner) - это User
        selectinload(AssetCatalog.owner),

        # 4. Подгружаем Склад (warehouse)
        selectinload(AssetCatalog.warehouse).options(
            selectinload(Warehouse.location),
            selectinload(Warehouse.preparer) # preparer in Warehouse
        ),

        # 5. Подгружаем Создателя записи (creator) - это User
        selectinload(AssetCatalog.creator)
    )

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

# Если нужна функция получения по ID:
async def get_catalog_item_by_id(db: AsyncSession, catalog_id: int) -> Optional[AssetCatalog]:
    result = await db.execute(
        select(AssetCatalog)
        .where(AssetCatalog.catalog_id == catalog_id)
        .options(
            # Те же самые options, что и выше
            selectinload(AssetCatalog.asset).options(
                selectinload(Asset.asset_type),
                selectinload(Asset.location_obj),
                selectinload(Asset.preparer),
                selectinload(Asset.checker),
                selectinload(Asset.software),
                selectinload(Asset.manufacturer).options(
                    selectinload(Vendor.vendor_class),
                    selectinload(Vendor.company).options(selectinload(Company.location_obj)),
                    selectinload(Vendor.creator)
                ),
                selectinload(Asset.vendor).options(
                    selectinload(Vendor.vendor_class),
                    selectinload(Vendor.company).options(selectinload(Company.location_obj)),
                    selectinload(Vendor.creator)
                )
            ),
            selectinload(AssetCatalog.model).options(
                selectinload(AssetModel.asset_class).options(
                    selectinload(AssetClass.asset_type),
                    selectinload(AssetClass.creator),
                    selectinload(AssetClass.updater)
                ),
                selectinload(AssetModel.creator),
                selectinload(AssetModel.updater)
            ),
            selectinload(AssetCatalog.owner),
            selectinload(AssetCatalog.warehouse).options(
                selectinload(Warehouse.location),
                selectinload(Warehouse.preparer)
            ),
            selectinload(AssetCatalog.creator)
        )
    )
    return result.scalar_one_or_none()