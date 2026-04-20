# from datetime import datetime
# from typing import List, Optional, Sequence, Any, Dict
# from sqlalchemy import select, func, distinct
# from sqlalchemy.ext.asyncio import AsyncSession
# import pandas as pd
# from sqlalchemy.orm import selectinload
#
# from app.models.AssetClass import AssetClass
# from app.models.AssetModel import AssetModel
# from app.models.AssetCatalog import AssetCatalog
# from app.models.Asset import Asset
#
# from app.schemas.catalog.ClassSchemas import AssetClassCreate, AssetClassUpdate
# from app.schemas.catalog.ModelSchemas import AssetModelCreate, AssetModelUpdate
# from app.schemas.catalog.CatalogSchemas import AssetCatalogCreate
# from app.models.Warehouse import Warehouse
# from app.models.Company import Company
# from app.models.Vendor import Vendor
#
# # === OPERATIONS ===
# # Вспомогательная функция для получения полных данных записи каталога (для снапшота)
# async def get_catalog_item_full(db: AsyncSession, catalog_id: int):
#     result = await db.execute(
#         select(AssetCatalog)
#         .where(AssetCatalog.catalog_id == catalog_id)
#         .options(
#             selectinload(AssetCatalog.asset),
#             selectinload(AssetCatalog.model).selectinload(AssetModel.asset_class)
#         )
#     )
#     return result.scalar_one_or_none()
#
#
# # === CLASS CRUD ===
# async def create_asset_class(db: AsyncSession, data: AssetClassCreate) -> AssetClass:
#     db_obj = AssetClass(**data.model_dump())
#     db.add(db_obj)
#     await db.commit()
#     await db.refresh(db_obj)
#     # Подгружаем связи для возврата полного объекта сразу после создания
#     await db.refresh(db_obj, attribute_names=["asset_type", "creator", "updater"])
#     return db_obj
#
# async def get_asset_class_by_id(db: AsyncSession, class_id: int) -> Optional[AssetClass]:
#     """Получает класс по ID со всеми связями"""
#     result = await db.execute(
#         select(AssetClass)
#         .where(AssetClass.class_id == class_id)
#         .options(
#             selectinload(AssetClass.asset_type),
#             selectinload(AssetClass.creator),
#             selectinload(AssetClass.updater)
#         )
#     )
#     return result.scalar_one_or_none()
#
# async def get_asset_classes(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[Any]:
#     """Получает список классов со связями"""
#     query = select(AssetClass).options(
#         selectinload(AssetClass.asset_type),
#         selectinload(AssetClass.creator),
#         selectinload(AssetClass.updater)
#     ).offset(skip).limit(limit)
#
#     result = await db.execute(query)
#     return result.scalars().all()
#
# async def update_asset_class(db: AsyncSession, class_id: int, data: AssetClassUpdate) -> Optional[AssetClass]:
#     obj = await get_asset_class_by_id(db, class_id) # Используем функцию с load
#     if not obj:
#         return None
#
#     update_data = data.model_dump(exclude_unset=True)
#     for k, v in update_data.items():
#         setattr(obj, k, v)
#
#     obj.updated_at = datetime.utcnow()
#
#     await db.commit()
#     await db.refresh(obj)
#     # После обновления связи могут сброситься, подгружаем снова
#     await db.refresh(obj, attribute_names=["asset_type", "creator", "updater"])
#     return obj
#
# async def delete_asset_class(db: AsyncSession, class_id: int) -> bool:
#     obj = await db.get(AssetClass, class_id)
#     if not obj: return False
#     await db.delete(obj)
#     await db.commit()
#     return True
#
#
# # === MODEL CRUD ===
# async def create_asset_model(db: AsyncSession, data: AssetModelCreate) -> AssetModel:
#     db_obj = AssetModel(**data.model_dump())
#     db.add(db_obj)
#     await db.commit()
#     await db.refresh(db_obj)
#     # Подгружаем связи для возврата полного объекта
#     await db.refresh(db_obj, attribute_names=["asset_class", "creator", "updater"])
#     return db_obj
#
# async def get_asset_model_by_id(db: AsyncSession, model_id: int) -> Optional[AssetModel]:
#     """Получает модель по ID со всеми глубокими связями"""
#     result = await db.execute(
#         select(AssetModel)
#         .where(AssetModel.model_id == model_id)
#         .options(
#             # Загружаем класс
#             selectinload(AssetModel.asset_class)
#             .options(
#                 # Внутри класса загружаем его тип и пользователей
#                 selectinload(AssetClass.asset_type),
#                 selectinload(AssetClass.creator),
#                 selectinload(AssetClass.updater)
#             ),
#             # Загружаем пользователей самой модели
#             selectinload(AssetModel.creator),
#             selectinload(AssetModel.updater)
#         )
#     )
#     return result.scalar_one_or_none()
#
# async def get_asset_models(
#         db: AsyncSession,
#         class_id: Optional[int] = None,
#         skip: int = 0,
#         limit: int = 50
# ) -> Sequence[Any]:
#     """Получает список моделей со всеми глубокими связями"""
#     query = select(AssetModel).options(
#         selectinload(AssetModel.asset_class)
#         .options(
#             selectinload(AssetClass.asset_type),
#             selectinload(AssetClass.creator),
#             selectinload(AssetClass.updater)
#         ),
#         selectinload(AssetModel.creator),
#         selectinload(AssetModel.updater)
#     )
#
#     if class_id:
#         query = query.where(AssetModel.class_id == class_id)
#
#     query = query.offset(skip).limit(limit)
#
#     result = await db.execute(query)
#     return result.scalars().all()
#
# async def update_asset_model(db: AsyncSession, model_id: int, data: AssetModelUpdate) -> Optional[AssetModel]:
#     obj = await get_asset_model_by_id(db, model_id) # Используем функцию с load
#     if not obj:
#         return None
#
#     update_data = data.model_dump(exclude_unset=True)
#     for k, v in update_data.items():
#         setattr(obj, k, v)
#
#     obj.updated_at = datetime.utcnow()
#
#     await db.commit()
#     await db.refresh(obj)
#     # После обновления связи могут сброситься, подгружаем снова
#     # Примечание: refresh с attribute_names может не подгрузить вложенные опции selectinload,
#     # поэтому для гарантированного результата лучше сделать отдельный запрос или использовать joinedload в модели.
#     # Но так как у нас selectinload в запросе получения, после commit() данные должны быть доступны,
#     # если сессия еще открыта. Для безопасности можно вызвать get_asset_model_by_id еще раз, но это лишний запрос.
#     # В данном случае, так как мы используем async_sessionmaker с expire_on_commit=False (в connection.py),
#     # объекты остаются прикрепленными. Однако, selectinload работает только при выполнении запроса.
#     # Чтобы получить свежие данные связей после обновления, проще всего сделать новый запрос:
#     return await get_asset_model_by_id(db, model_id)
#
#
# # === CATALOG & STATISTICS CRUD ===
# async def add_to_catalog(db: AsyncSession, data: AssetCatalogCreate) -> AssetCatalog:
#     # 1. Проверка: существует ли актив (можно оставить как есть, но лучше тоже с load если нужно)
#     asset = await db.get(Asset, data.asset_id)
#     if not asset:
#         raise ValueError("Asset not found")
#
#     # 2. Создаем объект
#     db_obj = AssetCatalog(**data.model_dump())
#     db.add(db_obj)
#     await db.commit()
#
#     # 3. ВАЖНО: После commit() нужно заново получить объект с подгруженными связями,
#     # так как db.refresh() по умолчанию не грузит relationships, если они не настроены на joined.
#     # Самый надежный способ — сделать отдельный запрос с options(selectinload(...))
#
#     result = await db.execute(
#         select(AssetCatalog)
#         .where(AssetCatalog.catalog_id == db_obj.catalog_id)
#         .options(
#             selectinload(AssetCatalog.asset).options(
#                 selectinload(Asset.asset_type),
#                 selectinload(Asset.location_obj),
#                 selectinload(Asset.preparer),
#                 selectinload(Asset.checker),
#                 selectinload(Asset.software),
#                 selectinload(Asset.manufacturer),
#                 selectinload(Asset.vendor)
#             ),
#             selectinload(AssetCatalog.model).options(
#                 selectinload(AssetModel.asset_class),
#                 selectinload(AssetModel.creator),
#                 selectinload(AssetModel.updater)
#             ),
#             selectinload(AssetCatalog.owner),
#             selectinload(AssetCatalog.warehouse).options(
#                 selectinload(Warehouse.location),
#                 selectinload(Warehouse.preparer)
#             ),
#             selectinload(AssetCatalog.creator)
#         )
#     )
#
#     full_obj = result.scalar_one_or_none()
#     if not full_obj:
#         raise ValueError("Failed to retrieve created catalog item with relations")
#
#     return full_obj
#
# async def get_catalog_stats_by_model(db: AsyncSession, model_id: int) -> dict:
#     """
#     Динамический подсчет количества активов для конкретной модели.
#     Возвращает: {total: int, in_stock: int, in_use: int, repair: int}
#     """
#     # Базовый запрос: считаем активы, связанные с этой моделью через таблицу catalog
#     # JOIN asset_catalog ac ON ac.model_id = :model_id
#     # JOIN assets a ON a.asset_id = ac.asset_id
#
#     subquery = select(AssetCatalog.asset_id).where(AssetCatalog.model_id == model_id)
#
#     total_q = select(func.count()).select_from(Asset).where(Asset.asset_id.in_(subquery))
#
#     # Статусы предполагаются строковыми, как в вашей модели (Приемка, На складе, Выдан...)
#     # Адаптируйте строки статусов под ваши реальные значения в Enum или строках
#     in_stock_q = select(func.count()).select_from(Asset).where(
#         Asset.asset_id.in_(subquery),
#         Asset.asset_status == 'WAREHOUSE' # Или 'На складе'
#     )
#     in_use_q = select(func.count()).select_from(Asset).where(
#         Asset.asset_id.in_(subquery),
#         Asset.asset_status == 'IN_USE' # Или 'Выдан'
#     )
#
#     total = await db.scalar(total_q) or 0
#     in_stock = await db.scalar(in_stock_q) or 0
#     in_use = await db.scalar(in_use_q) or 0
#
#     return {
#         "model_id": model_id,
#         "total_count": total,
#         "in_stock": in_stock,
#         "in_use": in_use,
#         "other": total - in_stock - in_use
#     }
#
# async def get_catalog_list(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[Any]:
#     """
#     Получает список записей каталога со ВСЕМИ глубокими связями.
#     """
#     query = select(AssetCatalog).options(
#         # 1. Подгружаем Актив (asset)
#         selectinload(AssetCatalog.asset).options(
#             selectinload(Asset.asset_type),
#             selectinload(Asset.location_obj),
#             selectinload(Asset.preparer),      # prepared_by user
#             selectinload(Asset.checker),       # checked_by user
#             selectinload(Asset.software),
#             selectinload(Asset.manufacturer).options( # Manufacturer is a Vendor
#                 selectinload(Vendor.vendor_class),
#                 selectinload(Vendor.company).options(
#                     selectinload(Company.location_obj)
#                 ),
#                 selectinload(Vendor.creator)
#             ),
#             selectinload(Asset.vendor).options(     # Vendor is a Vendor
#                 selectinload(Vendor.vendor_class),
#                 selectinload(Vendor.company).options(
#                     selectinload(Company.location_obj)
#                 ),
#                 selectinload(Vendor.creator)
#             )
#         ),
#
#         # 2. Подгружаем Модель (model)
#         selectinload(AssetCatalog.model).options(
#             selectinload(AssetModel.asset_class).options(
#                 selectinload(AssetClass.asset_type),
#                 selectinload(AssetClass.creator),
#                 selectinload(AssetClass.updater)
#             ),
#             selectinload(AssetModel.creator),
#             selectinload(AssetModel.updater)
#         ),
#
#         # 3. Подгружаем Владельца (owner) - это User
#         selectinload(AssetCatalog.owner),
#
#         # 4. Подгружаем Склад (warehouse)
#         selectinload(AssetCatalog.warehouse).options(
#             selectinload(Warehouse.location),
#             selectinload(Warehouse.preparer) # preparer in Warehouse
#         ),
#
#         # 5. Подгружаем Создателя записи (creator) - это User
#         selectinload(AssetCatalog.creator)
#     )
#
#     query = query.offset(skip).limit(limit)
#
#     result = await db.execute(query)
#     return result.scalars().all()
#
# async def get_catalog_item_by_id(db: AsyncSession, catalog_id: int) -> Optional[AssetCatalog]:
#     """ Получает элемент по ID со всеми встроенными значениями"""
#     result = await db.execute(
#         select(AssetCatalog)
#         .where(AssetCatalog.catalog_id == catalog_id)
#         .options(
#             # Те же самые options, что и выше
#             selectinload(AssetCatalog.asset).options(
#                 selectinload(Asset.asset_type),
#                 selectinload(Asset.location_obj),
#                 selectinload(Asset.preparer),
#                 selectinload(Asset.checker),
#                 selectinload(Asset.software),
#                 selectinload(Asset.manufacturer).options(
#                     selectinload(Vendor.vendor_class),
#                     selectinload(Vendor.company).options(selectinload(Company.location_obj)),
#                     selectinload(Vendor.creator)
#                 ),
#                 selectinload(Asset.vendor).options(
#                     selectinload(Vendor.vendor_class),
#                     selectinload(Vendor.company).options(selectinload(Company.location_obj)),
#                     selectinload(Vendor.creator)
#                 )
#             ),
#             selectinload(AssetCatalog.model).options(
#                 selectinload(AssetModel.asset_class).options(
#                     selectinload(AssetClass.asset_type),
#                     selectinload(AssetClass.creator),
#                     selectinload(AssetClass.updater)
#                 ),
#                 selectinload(AssetModel.creator),
#                 selectinload(AssetModel.updater)
#             ),
#             selectinload(AssetCatalog.owner),
#             selectinload(AssetCatalog.warehouse).options(
#                 selectinload(Warehouse.location),
#                 selectinload(Warehouse.preparer)
#             ),
#             selectinload(AssetCatalog.creator)
#         )
#     )
#     return result.scalar_one_or_none()


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
from app.schemas.catalog.CatalogSchemas import AssetCatalogCreate, AssetCatalogUpdate

from app.models.Warehouse import Warehouse
from app.models.Company import Company
from app.models.Vendor import Vendor

# Импорт функции логирования операций каталога
from app.database.crud_catalog_operations import create_catalog_operation_log


# === OPERATIONS & HELPERS ===

async def get_catalog_item_full(db: AsyncSession, catalog_id: int):
    """Получает запись каталога с минимальными связями для создания снапшота"""
    result = await db.execute(
        select(AssetCatalog)
        .where(AssetCatalog.catalog_id == catalog_id)
        .options(
            selectinload(AssetCatalog.asset),
            selectinload(AssetCatalog.model).selectinload(AssetModel.asset_class)
        )
    )
    return result.scalar_one_or_none()


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
    return await get_asset_model_by_id(db, model_id)


# === CATALOG & STATISTICS CRUD ===
async def add_to_catalog(db: AsyncSession, data: AssetCatalogCreate, current_user_id: Optional[int] = None) -> AssetCatalog:
    # 1. Проверка: существует ли актив
    asset = await db.get(Asset, data.asset_id)
    if not asset:
        raise ValueError("Asset not found")

    # 2. Создаем объект
    db_obj = AssetCatalog(**data.model_dump())
    db.add(db_obj)
    await db.commit()

    # 3. Получаем полный объект с связями для ответа и для снапшота
    full_obj = await get_catalog_item_by_id(db, db_obj.catalog_id)
    if not full_obj:
        raise ValueError("Failed to retrieve created catalog item with relations")

    # 4. Логирование операции CREATE
    try:
        inv_id = full_obj.asset.inventory_id if full_obj.asset else ""
        model_name = full_obj.model.model_name if full_obj.model else ""
        class_name = full_obj.model.asset_class.class_name if full_obj.model and full_obj.model.asset_class else ""

        await create_catalog_operation_log(
            db=db,
            catalog_id=db_obj.catalog_id,
            operation_type="CREATE",
            performed_by=current_user_id,
            new_values=data.model_dump(),
            comment="Запись добавлена в каталог",
            asset_inventory_id_snapshot=inv_id,
            model_name_snapshot=model_name,
            class_name_snapshot=class_name
        )
    except Exception as e:
        print(f"Error logging catalog creation: {e}")

    return full_obj

async def update_catalog_item(db: AsyncSession, catalog_id: int, data: AssetCatalogUpdate, current_user_id: Optional[int] = None) -> Optional[AssetCatalog]:
    """Обновляет запись каталога и логирует изменения"""
    obj = await db.get(AssetCatalog, catalog_id)
    if not obj:
        return None

    # Снимаем старый снапшот ДО обновления
    old_full = await get_catalog_item_full(db, catalog_id)
    old_inv = old_full.asset.inventory_id if old_full and old_full.asset else ""
    old_model = old_full.model.model_name if old_full and old_full.model else ""
    old_class = old_full.model.asset_class.class_name if old_full and old_full.model and old_full.model.asset_class else ""

    # Сохраняем старые значения ключевых полей для лога
    old_values = {
        "owner_id": obj.owner_id,
        "warehouse_id": obj.warehouse_id,
        "warranty_end_date": str(obj.warranty_end_date) if obj.warranty_end_date else None,
        "class_id": obj.class_id,
        "model_id": obj.model_id
    }

    # Применяем обновления
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(obj, key, value)

    await db.commit()

    # Снимаем новый снапшот ПОСЛЕ обновления
    new_full = await get_catalog_item_full(db, catalog_id)
    new_inv = new_full.asset.inventory_id if new_full and new_full.asset else ""
    new_model = new_full.model.model_name if new_full and new_full.model else ""
    new_class = new_full.model.asset_class.class_name if new_full and new_full.model and new_full.model.asset_class else ""

    # Логирование
    try:
        await create_catalog_operation_log(
            db=db,
            catalog_id=catalog_id,
            operation_type="UPDATE",
            performed_by=current_user_id,
            old_values=old_values,
            new_values=update_data,
            comment="Обновление записи каталога",
            asset_inventory_id_snapshot=new_inv,
            model_name_snapshot=new_model,
            class_name_snapshot=new_class
        )
    except Exception as e:
        print(f"Error logging catalog update: {e}")

    # Возвращаем полный объект с глубокими связями для ответа API
    return await get_catalog_item_by_id(db, catalog_id)


### ПОЧИНИТЬ УДАЛЕНИЕ
async def delete_catalog_item(db: AsyncSession, catalog_id: int, current_user_id: Optional[int] = None) -> bool:
    """Удаляет запись каталога и логирует операцию в одной транзакции"""
    obj = await db.get(AssetCatalog, catalog_id)
    if not obj:
        return False

    # 1. Снимаем снапшот перед удалением
    full_obj = await get_catalog_item_full(db, catalog_id)
    inv_id = full_obj.asset.inventory_id if full_obj and full_obj.asset else ""
    model_name = full_obj.model.model_name if full_obj and full_obj.model else ""
    class_name = full_obj.model.asset_class.class_name if full_obj and full_obj.model and full_obj.model.asset_class else ""

    # 2. Создаем объект лога операции (но пока не коммитим)
    from app.database.crud_catalog_operations import create_catalog_operation_log

    # Мы не можем использовать async функцию create_catalog_operation_log здесь напрямую,
    # так как она делает commit внутри себя. Нам нужно создать объект вручную,
    # чтобы добавить его в текущую сессию и сделать один общий commit.

    from app.models.CatalogOperation import CatalogOperation
    from datetime import datetime
    from app.database.crud_catalog_operations import _serialize_for_json # Используем хелпер сериализации

    log_entry = CatalogOperation(
        catalog_id=catalog_id,
        asset_inventory_id_snapshot=inv_id,
        model_name_snapshot=model_name,
        class_name_snapshot=class_name,
        operation_type="DELETE",
        performed_by=current_user_id,
        old_values=_serialize_for_json({"inventory_id": inv_id, "model": model_name, "class": class_name}),
        new_values=None,
        comment="Запись удалена из каталога",
        timestamp=datetime.utcnow()
    )

    db.add(log_entry)  # Добавляем лог в сессию
    await db.delete(obj)  # Добавляем удаление объекта в сессию

    try:
        await db.commit()  # Один коммит для обоих действий
        return True
    except Exception as e:
        await db.rollback() # В случае ошибки откатываем всё
        print(f"Error deleting catalog item and logging: {e}")
        return False

async def get_catalog_stats_by_model(db: AsyncSession, model_id: int) -> dict:
    """
    Динамический подсчет количества активов для конкретной модели.
    Возвращает: {total: int, in_stock: int, in_use: int, repair: int}
    """
    subquery = select(AssetCatalog.asset_id).where(AssetCatalog.model_id == model_id)

    total_q = select(func.count()).select_from(Asset).where(Asset.asset_id.in_(subquery))

    # Статусы предполагаются строковыми
    in_stock_q = select(func.count()).select_from(Asset).where(
        Asset.asset_id.in_(subquery),
        Asset.asset_status == 'WAREHOUSE'
    )
    in_use_q = select(func.count()).select_from(Asset).where(
        Asset.asset_id.in_(subquery),
        Asset.asset_status == 'IN_USE'
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
            selectinload(Asset.preparer),
            selectinload(Asset.checker),
            selectinload(Asset.software),
            selectinload(Asset.manufacturer).options(
                selectinload(Vendor.vendor_class),
                selectinload(Vendor.company).options(
                    selectinload(Company.location_obj)
                ),
                selectinload(Vendor.creator)
            ),
            selectinload(Asset.vendor).options(
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

        # 3. Подгружаем Владельца (owner)
        selectinload(AssetCatalog.owner),

        # 4. Подгружаем Склад (warehouse)
        selectinload(AssetCatalog.warehouse).options(
            selectinload(Warehouse.location),
            selectinload(Warehouse.preparer)
        ),

        # 5. Подгружаем Создателя записи (creator)
        selectinload(AssetCatalog.creator)
    )

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

async def get_catalog_item_by_id(db: AsyncSession, catalog_id: int) -> Optional[AssetCatalog]:
    """ Получает элемент по ID со всеми встроенными значениями"""
    result = await db.execute(
        select(AssetCatalog)
        .where(AssetCatalog.catalog_id == catalog_id)
        .options(
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