from datetime import datetime
from typing import List, Optional, Sequence, Any, Dict
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.AssetClass import AssetClass
from app.models.AssetModel import AssetModel
from app.models.AssetCatalog import AssetCatalog
from app.models.Asset import Asset
from app.schemas.catalog.ClassSchemas import AssetClassCreate, AssetClassUpdate
from app.schemas.catalog.ModelSchemas import AssetModelCreate, AssetModelUpdate
from app.schemas.catalog.CatalogSchemas import AssetCatalogCreate, AssetCatalogUpdate

from app.models.User import User
from app.models.Warehouse import Warehouse
from app.models.Company import Company
from app.models.Vendor import Vendor

# Импорт для логирования
from app.database.crud_catalog_operations import create_catalog_operation_log, _serialize_for_json
from app.models.CatalogOperation import CatalogOperation


# === HELPERS ===

async def get_catalog_item_full(db: AsyncSession, catalog_id: int):
    """Минимальные связи для снапшота"""
    result = await db.execute(
        select(AssetCatalog)
        .where(AssetCatalog.catalog_id == catalog_id)
        .options(
            selectinload(AssetCatalog.asset),
            selectinload(AssetCatalog.model).selectinload(AssetModel.asset_class)
        )
    )
    return result.scalar_one_or_none()

async def get_catalog_item_by_id(db: AsyncSession, catalog_id: int) -> Optional[AssetCatalog]:
    """Полные связи для ответа API"""
    result = await db.execute(
        select(AssetCatalog)
        .where(AssetCatalog.catalog_id == catalog_id)
        .options(
            selectinload(AssetCatalog.asset).options(
                selectinload(Asset.asset_type),
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
            # selectinload(AssetCatalog.warehouse).options(
            #     selectinload(Warehouse.location),
            #     selectinload(Warehouse.preparer)
            # ),
            selectinload(AssetCatalog.creator)
        )
    )
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
    result = await db.execute(
        select(AssetModel)
        .where(AssetModel.model_id == model_id)
        .options(
            selectinload(AssetModel.asset_class).options(
                selectinload(AssetClass.asset_type),
                selectinload(AssetClass.creator),
                selectinload(AssetClass.updater)
            ),
            selectinload(AssetModel.creator),
            selectinload(AssetModel.updater)
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
    from sqlalchemy import select
    from app.models.AssetCatalog import AssetCatalog

    # Проверяем, существует ли модель
    obj = await db.get(AssetModel, model_id)
    if not obj:
        return False

    # Проверяем, есть ли ссылки в каталоге (нельзя удалить используемую модель)
    result = await db.execute(
        select(AssetCatalog.catalog_id).where(AssetCatalog.model_id == model_id).limit(1)
    )
    if result.scalar_one_or_none():
        raise ValueError("Cannot delete model: it is referenced in AssetCatalog")

    # Жесткое удаление
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

    # ВАЖНО: Нам нужно получить ID нового объекта и связанные данные для лога.
    # Так как мы еще не сделали commit, db_obj.catalog_id может быть None (зависит от БД).
    # Но нам нужны данные связанного актива/модели для снапшота.
    # Получим их отдельным запросом по ID актива/модели из входных данных,
    # так как сам db_obj еще не имеет подгруженных отношений.

    # Получаем данные для снапшота заранее
    inv_id = asset.inventory_id

    model_res = await db.execute(select(AssetModel).where(AssetModel.model_id == data.model_id))
    model_obj = model_res.scalar_one_or_none()
    model_name = model_obj.model_name if model_obj else "Unknown"

    class_name = "Unknown"
    if model_obj:
        class_res = await db.execute(select(AssetClass).where(AssetClass.class_id == model_obj.class_id))
        class_obj = class_res.scalar_one_or_none()
        if class_obj:
            class_name = class_obj.class_name

    # 3. Создаем запись лога
    log_entry = CatalogOperation(
        catalog_id=db_obj.catalog_id, # Будет заполнено БД при flush/commit
        asset_inventory_id_snapshot=inv_id,
        model_name_snapshot=model_name,
        class_name_snapshot=class_name,
        # warehouse_name_snapshot=None, # При создании склада может не быть, или можно взять из data.warehouse_id если нужно
        owner_name_snapshot=None,     # Аналогично
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
    # Делаем это после коммита, чтобы избежать проблем с транзакцией
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
    old_model = old_full.model.model_name if old_full and old_full.model else ""
    old_class = old_full.model.asset_class.class_name if old_full and old_full.model and old_full.model.asset_class else ""

    # old_wh_name = old_full.warehouse.name if old_full and old_full.warehouse else "No Warehouse"
    old_owner_name = old_full.owner.owner if old_full and old_full.owner else "No Owner"

    old_values_dict = {
        "owner_id": obj.owner_id,
        # "warehouse_id": obj.warehouse_id,
        "warranty_end_date": str(obj.warranty_end_date) if obj.warranty_end_date else None,
        "class_id": obj.class_id,
        "model_id": obj.model_id
    }

    # 3. Применяем обновления к объекту
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(obj, key, value)

    # 4. Готовим новые значения для снапшота (берем из обновленного объекта или пересчитываем)
    # Для простоты возьмем актуальные названия, если они изменились (class_id/model_id)
    # Если class_id/model_id не менялись, можно использовать старые.
    # Но надежнее запросить заново или использовать логику:

    new_model_id = data.model_id if data.model_id is not None else obj.model_id
    new_class_id = None # Нужно будет запросить, если модель сменилась

    # Чтобы не усложнять, просто возьмем текущие значения из объекта obj после setattr,
    # но названия классов/моделей там не лежат.
    # Поэтому для снапшота лучше использовать те же методы, что и при удалении,
    # но так как мы еще не закоммитили, связи могут быть старыми.
    # Проще всего: если model_id изменился, найти новое название.

    final_model_name = old_model
    final_class_name = old_class

    if data.model_id and data.model_id != obj.model_id: # Если модель реально поменялась в данных
        m_res = await db.execute(select(AssetModel).where(AssetModel.model_id == data.model_id))
        m_obj = m_res.scalar_one_or_none()
        if m_obj:
            final_model_name = m_obj.model_name
            c_res = await db.execute(select(AssetClass).where(AssetClass.class_id == m_obj.class_id))
            c_obj = c_res.scalar_one_or_none()
            if c_obj: final_class_name = c_obj.class_name
    elif obj.model: # Если не менялась, берем из текущей связи (она должна быть загружена через get)
        # Но obj получен через db.get, связи нет. Поэтому используем old_full данные, если не менялось
        pass

    # Для надежности снапшота при обновлении лучше всего сделать запрос полных данных ПОСЛЕ коммита,
    # но лог должен быть внутри транзакции.
    # Компромисс: используем данные, которые знаем точно (ID), а названия берем старые,
    # если они не менялись. Если менялись - вычисляем новые.

    # Создаем запись лога
    log_entry = CatalogOperation(
        catalog_id=catalog_id,
        asset_inventory_id_snapshot=old_inv, # Инвентарник актива обычно не меняется через каталог
        model_name_snapshot=final_model_name,
        class_name_snapshot=final_class_name,
        # warehouse_name_snapshot=old_wh_name, # Можно улучшить, если warehouse_id менялся
        owner_name_snapshot=old_owner_name,  # Можно улучшить, если owner_id менялся
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
    import logging
    # 1. Получаем объект с полными данными для снапшота
    # Используем get_catalog_item_by_id, чтобы получить все имена (склад, владелец и т.д.)
    obj = await get_catalog_item_by_id(db, catalog_id)
    logging.info(obj)


    # 2. Формируем снимки
    inv_id = obj.asset.inventory_id if obj.asset else "Unknown"
    model_name = obj.model.model_name if obj.model else "Unknown"
    class_name = obj.model.asset_class.class_name if obj.model and obj.model.asset_class else "Unknown"
    # wh_name = obj.warehouse.name if obj.warehouse else "No Warehouse"
    owner_name = obj.owner.owner if obj.owner else "No Owner"

    # logging.info(f"{inv_id=} {model_name=} {class_name=} {wh_name=} {owner_name=}")

    detailed_old_values = {
        "catalog_id": obj.catalog_id,
        "asset": {"id": obj.asset_id, "inventory_id": inv_id, "name": obj.asset.name if obj.asset else None},
        "model": {"id": obj.model_id, "name": model_name, "class": class_name},
        # "warehouse": {"id": obj.warehouse_id, "name": wh_name},
        "owner": {"id": obj.owner_id, "name": owner_name},
        "warranty_end_date": str(obj.warranty_end_date) if obj.warranty_end_date else None
    }

    # 3. Создаем запись лога
    log_entry = CatalogOperation(
        catalog_id=catalog_id,
        asset_inventory_id_snapshot=inv_id,
        model_name_snapshot=model_name,
        class_name_snapshot=class_name,
        # warehouse_name_snapshot=wh_name,
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
        print(f"Error deleting catalog item: {e}")
        return False

async def get_catalog_list(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[Any]:
    query = select(AssetCatalog).options(
        selectinload(AssetCatalog.asset).options(
            selectinload(Asset.asset_type),
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
        # selectinload(AssetCatalog.warehouse).options(
        #     selectinload(Warehouse.location),
        #     selectinload(Warehouse.preparer)
        # ),
        selectinload(AssetCatalog.creator)
    )
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def get_catalog_stats_by_model(db: AsyncSession, model_id: int) -> dict:
    subquery = select(AssetCatalog.asset_id).where(AssetCatalog.model_id == model_id)
    total_q = select(func.count()).select_from(Asset).where(Asset.asset_id.in_(subquery))
    in_stock_q = select(func.count()).select_from(Asset).where(Asset.asset_id.in_(subquery), Asset.asset_status == 'WAREHOUSE')
    in_use_q = select(func.count()).select_from(Asset).where(Asset.asset_id.in_(subquery), Asset.asset_status == 'IN_USE')

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