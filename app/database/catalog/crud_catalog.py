from datetime import datetime
from typing import List, Optional, Sequence, Any, Dict
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd

from app.models.AssetClass import AssetClass
from app.models.AssetModel import AssetModel
from app.models.AssetCatalog import AssetCatalog
from app.models.Asset import Asset

from app.schemas.catalog.ClassSchemas import AssetClassCreate, AssetClassUpdate
from app.schemas.catalog.ModelSchemas import AssetModelCreate, AssetModelUpdate
from app.schemas.catalog.CatalogSchemas import AssetCatalogCreate, AssetCatalogUpdate
from app.models.User import User
from app.models.Warehouse import Warehouse


# === CLASS CRUD ===
async def create_asset_class(db: AsyncSession, data: AssetClassCreate) -> AssetClass:
    db_obj = AssetClass(**data.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_asset_classes(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[Any]:
    query = select(AssetClass).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def update_asset_class(db: AsyncSession, class_id: int, data: AssetClassUpdate) -> Optional[AssetClass]:
    obj = await db.get(AssetClass, class_id)
    if not obj: return None
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items(): setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(obj)
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
    return db_obj

async def get_asset_models(db: AsyncSession, class_id: Optional[int] = None, skip: int = 0, limit: int = 50) -> Sequence[Any]:
    query = select(AssetModel)
    if class_id:
        query = query.where(AssetModel.class_id == class_id)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def update_asset_model(db: AsyncSession, model_id: int, data: AssetModelUpdate) -> Optional[AssetModel]:
    obj = await db.get(AssetModel, model_id)
    if not obj: return None
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items(): setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(obj)
    return obj

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

async def get_catalog_list(db: AsyncSession, model_id: Optional[int] = None, skip: int = 0, limit: int = 50) -> Sequence[Any]:
    query = select(AssetCatalog)
    if model_id:
        query = query.where(AssetCatalog.model_id == model_id)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()