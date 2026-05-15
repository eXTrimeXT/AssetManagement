from datetime import datetime
from typing import List, Optional, Any, Sequence

from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.Asset import Asset
from app.models.Vendor import Vendor
from app.models.AssetType import AssetType
from app.models.Software import Software
from app.models.Warehouse import Warehouse
from app.schemas.assets.AssetCreate import AssetCreate
from app.schemas.assets.AssetUpdate import AssetUpdate
from app.database.crud_operations import create_operation_log


""" ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ """
async def get_active_asset(db: AsyncSession, asset_id: int) -> Any | None:
    """
    Получает актив по ID.
    Raises HTTPException 404, если актив не найден или удален (soft delete).
    """
    # Примечание: В CRUD слое мы обычно возвращаем None или выбрасываем исключение.
    # Так как в роутере используется HTTPException, здесь мы тоже будем его использовать
    # или вернем None, а обработку оставим на сервисном слое/роутере.
    # Для совместимости с текущей логикой роутера, вернем объект или None,
    # но лучше вынести проверку существования отдельно.

    result = await db.execute(
        select(Asset)
        .where(Asset.asset_id == asset_id)
        .where(Asset.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()

async def get_asset_with_deleted(db: AsyncSession, asset_id: int) -> Optional[Asset]:
    """ Получает актив по ID, включая мягко удаленные """
    result = await db.execute(select(Asset).where(Asset.asset_id == asset_id))
    return result.scalar_one_or_none()

async def check_duplicate_inventory_id(db: AsyncSession, inventory_id: str, exclude_id: Optional[int] = None) -> bool:
    """
    Проверяет, существует ли актив с таким инвентарным номером.
    Возвращает True, если дубликат найден.
    """
    query = select(Asset).where(Asset.inventory_id == inventory_id)
    if exclude_id:
        query = query.where(Asset.asset_id != exclude_id)

    result = await db.execute(query)
    return result.scalar_one_or_none() is not None

async def check_duplicate_serial_number(db: AsyncSession, serial_number: str, exclude_id: Optional[int] = None) -> bool:
    """
    Проверяет, существует ли актив с таким серийным номером.
    Возвращает True, если дубликат найден.
    """
    query = select(Asset).where(Asset.serial_number == serial_number)
    if exclude_id:
        query = query.where(Asset.asset_id != exclude_id)

    result = await db.execute(query)
    return result.scalar_one_or_none() is not None

async def check_parent_exists(db: AsyncSession, parent_id: int) -> bool:
    """ Проверяет существование родительского актива """
    result = await db.execute(select(Asset).where(Asset.asset_id == parent_id))
    return result.scalar_one_or_none() is not None

async def get_vendor_by_id(db: AsyncSession, vendor_id: int) -> bool:
    """ Проверяет существование вендора """
    result = await db.execute(select(Vendor).where(Vendor.vendor_id == vendor_id))
    return result.scalar_one_or_none() is not None

async def get_asset_type(db: AsyncSession, asset_type: int) -> bool:
    """ Проверяет существование типа актива """
    result = await db.execute(select(AssetType).where(AssetType.asset_type_id == asset_type))
    return result.scalar_one_or_none() is not None


""" CRUD ОПЕРАЦИИ """
async def create_asset(db: AsyncSession, asset_in: AssetCreate, current_user_id: Optional[int] = None) -> Asset:
    """
    Создает новый актив в базе данных.
    """
    db_asset = Asset(**asset_in.model_dump())
    db.add(db_asset)
    await db.commit()
    await db.refresh(db_asset)
    # Логирование создания
    await create_operation_log(
        db=db,
        asset_id=db_asset.asset_id,
        operation_type="CREATE",
        performed_by=current_user_id,
        new_values=asset_in.model_dump(),
        comment="Актив создан",
        inventory_id_snapshot=db_asset.inventory_id,
        name_snapshot=db_asset.name
    )
    return db_asset

async def get_assets_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        asset_status: Optional[str] = None,
        asset_type_id: Optional[int] = None,
        deleted: bool = False
) -> Sequence[Any]:
    """
    Получает список активов с применением фильтров и пагинации.
    """
    query = select(Asset)

    # Фильтр по удалению
    if not deleted:
        query = query.where(Asset.deleted_at.is_(None))

    # Фильтры
    if asset_status:
        query = query.where(Asset.asset_status == asset_status)
    if asset_type_id:
        query = query.where(Asset.asset_type_id == asset_type_id)


    # Пагинация
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

async def get_asset_by_id(db: AsyncSession, asset_id: int) -> Optional[Asset]:
    """
    Получает полный объект актива со ВСЕМИ связями для детального ответа.
    """
    result = await db.execute(
        select(Asset)
        .where(Asset.asset_id == asset_id)
        .where(Asset.deleted_at.is_(None))
        .options(
            selectinload(Asset.asset_type),       # Загрузка типа
            selectinload(Asset.warehouse_obj),    # Загрузка склада (вместо локации)
            selectinload(Asset.preparer),         # Загрузка подготовившего (User)
            selectinload(Asset.checker),          # Загрузка проверившего (User)
            selectinload(Asset.software).options(selectinload(Software.installer)),         # Загрузка ПО

            selectinload(Asset.manufacturer),     # Загрузка производителя (Vendor)
            selectinload(Asset.vendor),           # Загрузка поставщика (Vendor)

            # Для Vendor нужно также загрузить его внутренние связи, если они не lazy='joined' в модели
            # Если в модели Vendor указано lazy='joined' для company и vendor_class, то этого достаточно.
            # Если нет, то нужно добавлять:
            selectinload(Asset.manufacturer).selectinload(Vendor.company),
            selectinload(Asset.manufacturer).selectinload(Vendor.vendor_class),
            selectinload(Asset.manufacturer).selectinload(Vendor.creator),
        )
    )
    return result.scalar_one_or_none()

async def update_asset(db: AsyncSession, asset_id: int, asset_data: AssetUpdate, current_user_id: Optional[int] = None) -> Optional[Asset]:
    """
    Обновляет поля актива и записывает историю изменений.
    """
    # Получаем актив
    asset = await get_active_asset(db, asset_id)
    if not asset:
        return None

    # Фиксируем старые значения ДО обновления
    old_values = {}

    # Собираем только те поля, которые пришли в запросе на обновление (exclude_unset=True)
    update_data = asset_data.model_dump(exclude_unset=True)

    for key in update_data.keys():
        if hasattr(asset, key):
            # Сохраняем старое значение
            old_val = getattr(asset, key)
            old_values[key] = old_val

    # Применяем обновления
    for key, value in update_data.items():
        setattr(asset, key, value)

    # Обновляем timestamp вручную, если он не обновляется автоматически onupdate
    asset.updated_at = datetime.utcnow()

    await db.commit()

    # Логируем операцию UPDATE
    if old_values: # Пишем лог только если что-то реально изменилось
        try:
            await create_operation_log(
                db=db,
                asset_id=asset_id,
                operation_type="UPDATE",
                performed_by=current_user_id,
                old_values=old_values,
                new_values=update_data,
                comment="Обновление данных актива",
                inventory_id_snapshot=asset.inventory_id,
                name_snapshot=asset.name
            )
        except Exception as e:
            # Если логирование упало, мы не должны ломать основное обновление,
            # но в продакшене лучше залогировать ошибку в stderr/logger
            print(f"Error logging operation: {e}")

    # Возвращаем обновленный актив с полными связями
    # Важно перегрузить его через get_asset_by_id, чтобы избежать MissingGreenlet при сериализации связей
    updated_asset_full = await get_asset_by_id(db, asset_id)

    return updated_asset_full

async def deactivate_asset(db: AsyncSession, asset_id: int, current_user_id: Optional[int] = None) -> Optional[Asset]:
    asset = await get_active_asset(db, asset_id)
    if not asset:
        return None

    asset.deleted_at = datetime.now()
    asset.updated_at = datetime.now()

    await db.commit()

    # Логирование деактивации
    try:
        await create_operation_log(
            db=db,
            asset_id=asset_id,
            operation_type="DEACTIVATE",
            performed_by=current_user_id,
            old_values={"deleted_at": None},
            new_values={"deleted_at": asset.deleted_at.isoformat()},
            comment="Актив деактивирован",
            inventory_id_snapshot=asset.inventory_id,
            name_snapshot=asset.name
        )
    except Exception as e:
        print(f"Error logging deactivation: {e}")

    await db.refresh(asset)
    return asset

async def activate_asset(db: AsyncSession, asset_id: int, current_user_id: Optional[int] = None) -> Optional[Asset]:
    """
    Восстановление актива (сброс deleted_at).
    """
    asset = await get_asset_with_deleted(db, asset_id)
    if not asset:
        return None

    # Если уже активен, возвращаем None или можно выбросить ошибку,
    # но логика проверки обычно в роутере. Здесь просто обновляем.
    if asset.deleted_at is None:
        return asset

    # сохраняем верную дату перед изменением
    old_date_deleted_at = asset.deleted_at
    asset.deleted_at = None
    asset.updated_at = datetime.now()

    await db.commit()

    # Логирование активации
    try:
        await create_operation_log(
            db=db,
            asset_id=asset_id,
            operation_type="ACTIVATE",
            performed_by=current_user_id,
            old_values={"deleted_at": old_date_deleted_at.isoformat()},
            new_values={"deleted_at": None, "updated_at": asset.updated_at},
            comment="Актив активирован",
            inventory_id_snapshot=asset.inventory_id,
            name_snapshot=asset.name
        )
    except Exception as e:
        print(f"Error logging activation: {e}")
    await db.refresh(asset)
    return asset

async def hard_delete_asset(db: AsyncSession, asset_id: int, current_user_id: Optional[int] = None) -> bool:
    """
    Жесткое удаление актива и всех его детей рекурсивно с полным логированием.
    """
    # Получаем родителя
    parent_asset = await get_asset_with_deleted(db, asset_id)
    if not parent_asset:
        return False

    # Собираем IDs всех детей
    async def collect_all_ids(parent_id: int) -> list[int]:
        result = await db.execute(select(Asset.asset_id).where(Asset.parent_id == parent_id))
        child_ids = [row[0] for row in result.fetchall()]
        all_ids = []
        for cid in child_ids:
            all_ids.extend(await collect_all_ids(cid))
        all_ids.extend(child_ids)
        return all_ids

    child_ids = await collect_all_ids(asset_id)
    all_ids_to_delete = child_ids + [asset_id]

    if not all_ids_to_delete:
        return False

    # Собираем информацию для логов ПЕРЕД удалением
    # Пример расширения запроса для сбора всех важных полей перед удалением
    assets_info_result = await db.execute(
        select(
            Asset.asset_id,
            Asset.parent_id,
            Asset.inventory_id,
            Asset.name,
            Asset.serial_number,
            Asset.asset_status,
            Asset.price,
            Asset.warehouse_id,  # Заменено location_id на warehouse_id
            Asset.manufacturer_id,
            Asset.vendor_id
        )
        .where(Asset.asset_id.in_(all_ids_to_delete))
    )

    # Преобразование в удобный словарь
    assets_data_map = {}
    for row in assets_info_result.fetchall():
        # row._mapping позволяет обращаться к колонкам по имени
        d = dict(row._mapping)
        assets_data_map[d['asset_id']] = d

    # 4. Логируем удаление КАЖДОГО актива (и родителя, и детей)
    for aid in all_ids_to_delete:
        info = assets_data_map.get(aid, {})
        try:
            await create_operation_log(
                db=db,
                asset_id=aid, # ID может стать невалидным после удаления, но мы сохранили snapshot
                operation_type="DELETE",
                performed_by=current_user_id,
                old_values=info,
                new_values=None,
                comment="Hard Delete",
                # === СОХРАНЯЕМ СНАПШОТ В ИСТОРИЮ ===
                inventory_id_snapshot=info.get("inventory_id"),
                name_snapshot=info.get("name")
            )
        except Exception as e:
            print(f"Error logging deletion for asset {aid}: {e}")

    # 5. Физическое удаление
    if child_ids:
        await db.execute(delete(Asset).where(Asset.asset_id.in_(child_ids)))

    await db.delete(parent_asset)
    await db.commit()

    return True

async def get_all_asset_children_recursive(db: AsyncSession, asset_id: int, max_depth: Optional[int] = None) -> List[dict]:
    """
    Получает всех дочерних активов рекурсивно с использованием CTE PostgreSQL.
    Возвращает список словарей с актуальными полями (warehouse_id вместо location, + seller, price).
    """
    # Проверяем существование родителя
    parent = await db.get(Asset, asset_id)
    if not parent or parent.deleted_at:
        return []

    # Формирование RAW SQL запроса
    base_query = """
                 WITH RECURSIVE asset_tree AS (
                     -- Базовый случай: прямые дети указанного актива
                     SELECT
                         asset_id, name, inventory_id, serial_number, asset_status, asset_type_id,
                         warehouse_id, parent_id, deleted_at, software_id, price, 1 AS depth
                     FROM assets
                     WHERE parent_id = :root_id AND deleted_at IS NULL

                     UNION ALL

                     -- Рекурсивный случай: дети детей
                     SELECT
                         a.asset_id, a.name, a.inventory_id, a.serial_number, a.asset_status, a.asset_type_id,
                         a.warehouse_id, a.parent_id, a.deleted_at, a.software_id, a.price, at.depth + 1
                     FROM assets a
                              INNER JOIN asset_tree at ON a.parent_id = at.asset_id
                     WHERE a.deleted_at IS NULL \
                 """

    if max_depth:
        base_query += " AND at.depth < :max_depth"

    base_query += """
    )
    SELECT * FROM asset_tree
    ORDER BY depth, asset_id
    """

    params = {"root_id": asset_id}
    if max_depth:
        params["max_depth"] = max_depth

    final_query = text(base_query)

    result = await db.execute(final_query, params)
    rows = result.fetchall()

    # 3. Конвертация в список словарей
    children = []
    for row in rows:
        children.append({
            "asset_id": row.asset_id,
            "name": row.name,
            "inventory_id": row.inventory_id,
            "serial_number": row.serial_number,
            "asset_status": row.asset_status,
            "asset_type_id": row.asset_type_id,
            "warehouse_id": row.warehouse_id,  # Заменено location_id на warehouse_id
            "parent_id": row.parent_id,
            "software_id": row.software_id,
            "seller": row.seller,
            "price": row.price
        })

    return children