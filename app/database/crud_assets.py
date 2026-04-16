from datetime import datetime
from typing import List, Optional, Any, Sequence
from unittest import result

from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.Asset import Asset
from app.models.Vendor import Vendor
from app.models.AssetType import AssetType
from app.schemas.assets.AssetCreate import AssetCreate
from app.schemas.assets.AssetUpdate import AssetUpdate


# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ПОИСКА
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
    """
    Получает актив по ID, включая мягко удаленные.
    """
    result = await db.execute(
        select(Asset)
        .where(Asset.asset_id == asset_id)
    )
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
    """
    Проверяет существование родительского актива.
    """
    result = await db.execute(select(Asset).where(Asset.asset_id == parent_id))
    return result.scalar_one_or_none() is not None

async def get_vendor_by_id(db: AsyncSession, vendor_id: int) -> bool:
    """
    Проверяет существование вендора.
    """
    result = await db.execute(select(Vendor).where(Vendor.vendor_id == vendor_id))
    return result.scalar_one_or_none() is not None

async def get_asset_type(db: AsyncSession, asset_type: int) -> bool:
    """
    Проверяет существование типа актива
    """
    result = await db.execute(select(AssetType).where(AssetType.asset_type_id == asset_type))
    return result.scalar_one_or_none()


# CRUD ОПЕРАЦИИ
async def create_asset(db: AsyncSession, asset_in: AssetCreate) -> Asset:
    """
    Создает новый актив в базе данных.
    """
    db_asset = Asset(**asset_in.model_dump())
    db.add(db_asset)
    await db.commit()
    await db.refresh(db_asset)
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

# async def get_asset_by_id(db: AsyncSession, asset_id: int) -> Optional[Asset]:
#     """
#     Получает полный объект актива с подгрузкой связанных типов (asset_type).
#     Только активные (не удаленные) активы.
#     """
#     result = await db.execute(
#         select(Asset)
#         .where(Asset.asset_id == asset_id)
#         .where(Asset.deleted_at.is_(None))
#         .options(selectinload(Asset.asset_type))
#     )
#     return result.scalar_one_or_none()

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
            selectinload(Asset.location_obj),     # Загрузка локации
            selectinload(Asset.preparer),         # Загрузка подготовившего (User)
            selectinload(Asset.checker),          # Загрузка проверившего (User)
            selectinload(Asset.software),         # Загрузка ПО
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


async def update_asset(db: AsyncSession, asset_id: int, asset_data: AssetUpdate) -> Optional[Asset]:
    """
    Обновляет поля актива.
    """
    asset = await get_active_asset(db, asset_id)
    if not asset:
        return None

    update_data = asset_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(asset, key, value)

    await db.commit()
    await db.refresh(asset)
    return asset


async def deactivate_asset(db: AsyncSession, asset_id: int) -> Optional[Asset]:
    """
    Мягкое удаление актива (установка deleted_at).
    """
    asset = await get_active_asset(db, asset_id)
    if not asset:
        return None

    asset.deleted_at = datetime.now()
    asset.updated_at = datetime.now()

    await db.commit()
    await db.refresh(asset)
    return asset


async def activate_asset(db: AsyncSession, asset_id: int) -> Optional[Asset]:
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

    asset.deleted_at = None
    asset.updated_at = datetime.now()

    await db.commit()
    await db.refresh(asset)
    return asset


async def hard_delete_asset(db: AsyncSession, asset_id: int) -> bool:
    """
    Жесткое удаление актива и всех его детей рекурсивно.
    Возвращает True, если удаление прошло успешно.
    """
    asset = await get_asset_with_deleted(db, asset_id)
    if not asset:
        return False

    # Сбор всех ID активов (родитель + дети рекурсивно)
    async def collect_child_ids(parent_id: int) -> list[int]:
        result = await db.execute(select(Asset.asset_id).where(Asset.parent_id == parent_id))
        child_ids = [row[0] for row in result.fetchall()]
        all_ids = child_ids.copy()
        for child_id in child_ids:
            all_ids.extend(await collect_child_ids(child_id))
        return all_ids

    child_ids = await collect_child_ids(asset_id)
    all_ids = [asset_id] + child_ids

    # Удаляем дочерние активы (каскадно через SQL delete, так как ORM cascade может не сработать корректно при ручном обходе)
    # В модели указан ondelete="CASCADE" для parent_id, но для безопасности явно удаляем детей
    if child_ids:
        # Удаляем от листьев к корню, чтобы избежать конфликтов FK, если CASCADE не настроен на уровне БД строго
        # Однако, так как у нас SQLAlchemy ORM, лучше использовать ORM delete для триггеров,
        # но массовое удаление быстрее через execute(delete...)

        # Примечание: В исходном коде было reverse().
        # Если в БД настроен ON DELETE CASCADE на FK parent_id, то удаление родителя удалит детей.
        # Но в коде автора явное удаление детей. Оставим логику автора.

        child_ids.reverse()
        await db.execute(delete(Asset).where(Asset.asset_id.in_(child_ids)))

    # Удаляем основной актив
    await db.delete(asset)
    await db.commit()
    return True

async def get_all_asset_children_recursive(
        db: AsyncSession,
        asset_id: int,
        max_depth: Optional[int] = None
) -> List[dict]:
    """
    Получает всех дочерних активов рекурсивно с использованием CTE PostgreSQL.
    Возвращает список словарей с актуальными полями (location_id вместо location, + seller, price).
    """
    # 1. Проверяем существование родителя
    parent = await db.get(Asset, asset_id)
    if not parent or parent.deleted_at:
        return []

        # 2. Формирование RAW SQL запроса
    # ИЗМЕНЕНИЯ:
    # - location заменен на location_id
    # - добавлены seller и price
    base_query = """
                 WITH RECURSIVE asset_tree AS (
                     -- Базовый случай: прямые дети указанного актива
                     SELECT
                         asset_id, name, inventory_id, serial_number, asset_status, asset_type_id,
                         location_id, parent_id, deleted_at, software_id, price, 1 AS depth
                     FROM assets
                     WHERE parent_id = :root_id AND deleted_at IS NULL

                     UNION ALL

                     -- Рекурсивный случай: дети детей
                     SELECT
                         a.asset_id, a.name, a.inventory_id, a.serial_number, a.asset_status, a.asset_type_id,
                         a.location_id, a.parent_id, a.deleted_at, a.software_id, a.price, at.depth + 1
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
            "location_id": row.location_id,  # Обновлено: было location
            "parent_id": row.parent_id,
            "software_id": row.software_id,
            "seller": row.seller,           # Добавлено
            "price": row.price              # Добавлено
        })

    return children