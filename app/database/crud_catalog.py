import logging
from datetime import datetime
from typing import Optional, Sequence, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.AssetClass import AssetClass
from app.models.AssetModel import AssetModel
from app.models.AssetCatalog import AssetCatalog
from app.models.Asset import Asset
from app.schemas.catalog.ClassSchemas import AssetClassCreate, AssetClassUpdate
from app.schemas.catalog.ModelSchemas import AssetModelCreate, AssetModelUpdate
from app.schemas.catalog.CatalogSchemas import AssetCatalogCreate, AssetCatalogUpdate
# Импорт для логирования
from app.database.crud_catalog_operations import _serialize_for_json
from app.models.CatalogOperation import CatalogOperation

# === HELPERS ===
async def get_catalog_item_full(db: AsyncSession, catalog_id: int):
    """Минимальные связи для снапшота"""
    result = await db.execute(
        select(AssetCatalog)
        .where(AssetCatalog.catalog_id == catalog_id)
        .options(
            selectinload(AssetCatalog.asset),
        )
    )
    return result.scalar_one_or_none()

async def get_catalog_item_by_id(db: AsyncSession, catalog_id: int) -> Optional[AssetCatalog]:
    """
    Получает запись каталога по ID с загруженными связями для фильтрации по правам и ответа API.
    Правильный путь: AssetCatalog → asset → model → asset_class → asset_type
    """
    query = select(AssetCatalog).where(AssetCatalog.catalog_id == catalog_id).options(
        # === Загружаем цепочку для фильтрации по asset_type.en_name ===
        # AssetCatalog → asset → model → asset_class → asset_type
        selectinload(AssetCatalog.asset)
        .selectinload(Asset.model)
        .selectinload(AssetModel.asset_class)
        .selectinload(AssetClass.asset_type),
        # Остальные связи для ответа API
        selectinload(AssetCatalog.owner),
        selectinload(AssetCatalog.creator)
    )

    result = await db.execute(query)
    return result.scalar_one_or_none()

# === CLASS CRUD ===
async def create_asset_class(db: AsyncSession, data: AssetClassCreate) -> AssetClass:
    db_obj = AssetClass(**data.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    await db.refresh(db_obj, attribute_names=["asset_type", "creator", "updater"])
    return db_obj

async def get_asset_class_by_id(db: AsyncSession, class_id: int) -> Optional[AssetClass]:
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
    query = select(AssetClass).options(
        selectinload(AssetClass.asset_type),
        selectinload(AssetClass.creator),
        selectinload(AssetClass.updater)
    ).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def update_asset_class(db: AsyncSession, class_id: int, data: AssetClassUpdate) -> Optional[AssetClass]:
    obj = await get_asset_class_by_id(db, class_id)
    if not obj: return None
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items(): setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(obj)
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
    await db.refresh(db_obj, attribute_names=["asset_class", "creator", "updater"])
    return db_obj

async def get_asset_model_by_id(db: AsyncSession, model_id: int) -> Optional[AssetModel]:
    """Получает модель с загруженными связями для проверки прав"""
    result = await db.execute(
        select(AssetModel)
        .where(AssetModel.model_id == model_id)
        .options(
            # === Загружаем цепочку до asset_type для проверки прав ===
            selectinload(AssetModel.asset_class)
            .selectinload(AssetClass.asset_type)
        )
    )
    return result.scalar_one_or_none()

async def get_asset_models(db: AsyncSession, class_id: Optional[int] = None, skip: int = 0, limit: int = 50) -> Sequence[Any]:
    query = select(AssetModel).options(
        selectinload(AssetModel.asset_class).options(
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
    obj = await get_asset_model_by_id(db, model_id)
    if not obj: return None
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items(): setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    await db.commit()
    return await get_asset_model_by_id(db, model_id)

async def delete_asset_model(db: AsyncSession, model_id: int) -> bool:
    """
    Жесткое удаление модели оборудования.
    Возвращает True если удалено, False если не найдено.
    Выбрасывает ValueError если модель используется в каталоге (есть связанные AssetCatalog).
    """
    # Проверяем, существует ли модель
    obj = await db.get(AssetModel, model_id)
    if not obj:
        return False

    # Жесткое удаление (проверка ссылок удалена вместе с model_id из каталога)
    await db.delete(obj)
    await db.commit()
    return True

# === CATALOG CRUD ===
async def add_to_catalog(db: AsyncSession, data: AssetCatalogCreate, current_user_id: Optional[int] = None) -> AssetCatalog:
    """
    Создает запись в каталоге и логирует операцию CREATE в одной транзакции.
    """
    # 1. Проверки
    asset = await db.get(Asset, data.asset_id)
    if not asset:
        raise ValueError("Asset not found")
    existing = await db.execute(select(AssetCatalog).where(AssetCatalog.asset_id == data.asset_id))
    if existing.scalar_one_or_none():
        raise ValueError(f"Asset {data.asset_id} already in catalog")

    # 2. Создаем основной объект
    db_obj = AssetCatalog(**data.model_dump())
    db.add(db_obj)

    # Получаем данные для снапшота заранее
    inv_id = asset.inventory_id

    # 3. Создаем запись лога
    log_entry = CatalogOperation(
        catalog_id=db_obj.catalog_id,
        asset_inventory_id_snapshot=inv_id,
        owner_name_snapshot=None,
        operation_type="CREATE",
        performed_by=current_user_id,
        old_values=None,
        new_values=_serialize_for_json(data.model_dump()),
        comment="Запись добавлена в каталог",
        timestamp=datetime.utcnow()
    )
    db.add(log_entry)

    # 4. Единый коммит для создания записи и лога
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise e

    # 5. Возвращаем полный объект с подгруженными связями для ответа API
    full_obj = await get_catalog_item_by_id(db, db_obj.catalog_id)
    if not full_obj:
        raise ValueError("Failed to retrieve created catalog item")

    return full_obj

async def update_catalog_item(
        db: AsyncSession,
        catalog_id: int,
        data: AssetCatalogUpdate,
        current_user_id: Optional[int] = None
) -> Optional[AssetCatalog]:
    """
    Обновляет запись каталога и логирует операцию UPDATE в одной транзакции.
    """
    # 1. Получаем текущий объект
    obj = await db.get(AssetCatalog, catalog_id)
    if not obj:
        return None

    # 2. Снимаем старые значения для лога ДО обновления
    old_full = await get_catalog_item_full(db, catalog_id)
    old_inv = old_full.asset.inventory_id if old_full and old_full.asset else ""
    old_owner_name = old_full.owner.owner if old_full and old_full.owner else "No Owner"

    old_values_dict = {
        "owner_id": obj.owner_id,
        "warranty_end_date": str(obj.warranty_end_date) if obj.warranty_end_date else None,
    }

    # 3. Применяем обновления к объекту
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(obj, key, value)

    # 4. Создаем запись лога
    log_entry = CatalogOperation(
        catalog_id=catalog_id,
        asset_inventory_id_snapshot=old_inv,
        owner_name_snapshot=old_owner_name,
        operation_type="UPDATE",
        performed_by=current_user_id,
        old_values=_serialize_for_json(old_values_dict),
        new_values=_serialize_for_json(update_data),
        comment="Обновление записи каталога",
        timestamp=datetime.utcnow()
    )
    db.add(log_entry)

    # 5. Единый коммит
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        return None

    # 6. Возвращаем полный обновленный объект
    return await get_catalog_item_by_id(db, catalog_id)

async def delete_catalog_item(db: AsyncSession, catalog_id: int, current_user_id: Optional[int] = None) -> bool:
    """
    Удаляет запись каталога с логированием.
    """
    # 1. Получаем объект с полными данными для снапшота
    obj = await get_catalog_item_by_id(db, catalog_id)
    logging.info(obj)

    # 2. Формируем снимки
    inv_id = obj.asset.inventory_id if obj.asset else "Unknown"
    owner_name = obj.owner.owner if obj.owner else "No Owner"

    detailed_old_values = {
        "catalog_id": obj.catalog_id,
        "asset": {"id": obj.asset_id, "inventory_id": inv_id, "name": obj.asset.name if obj.asset else None},
        "owner": {"id": obj.owner_id, "name": owner_name},
        "warranty_end_date": str(obj.warranty_end_date) if obj.warranty_end_date else None
    }

    # 3. Создаем запись лога
    log_entry = CatalogOperation(
        catalog_id=catalog_id,
        asset_inventory_id_snapshot=inv_id,
        owner_name_snapshot=owner_name,
        operation_type="DELETE",
        performed_by=current_user_id,
        old_values=_serialize_for_json(detailed_old_values),
        new_values=None,
        comment=f"Запись каталога для актива {inv_id} удалена",
        timestamp=datetime.utcnow()
    )

    db.add(log_entry)

    # 4. Удаляем объект каталога
    await db.delete(obj)

    try:
        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        print(f"Error deleting catalog item: {e}!")
        return False

async def get_catalog_list(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[Any]:
    """
    Получает список записей каталога с загруженными связями для фильтрации по правам.
    Правильный путь: AssetCatalog → asset → model → asset_class → asset_type
    """
    query = select(AssetCatalog).options(
        # === Загружаем цепочку для фильтрации по asset_type.en_name ===
        # AssetCatalog → asset → model → asset_class → asset_type
        selectinload(AssetCatalog.asset)
        .selectinload(Asset.model)
        .selectinload(AssetModel.asset_class)
        .selectinload(AssetClass.asset_type),
        # Остальные связи для ответа API
        selectinload(AssetCatalog.owner),
        selectinload(AssetCatalog.creator)
    )

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()