from datetime import datetime
from typing import List, Optional, Any, Sequence

from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.Asset import Asset
from app.models.Vendor import Vendor
from app.models.Software import Software
from app.models.AssetModel import AssetModel
from app.models.AssetClass import AssetClass
from app.schemas.assets.AssetCreate import AssetCreate
from app.schemas.assets.AssetUpdate import AssetUpdate
from app.database.crud_operations import create_operation_log
from app.models.AssetPosition import AssetPosition
from app.models.AssetType import AssetType
from app.models.AssetCatalog import AssetCatalog
from app.schemas.assets.AssetUpdateWithUsers import AssetUpdateWithUsers

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

async def get_asset_model(db: AsyncSession, model_id: int) -> bool:
    """ Проверяет существование модели актива """
    result = await db.execute(select(AssetModel).where(AssetModel.model_id == model_id))
    return result.scalar_one_or_none() is not None


""" CRUD ОПЕРАЦИИ """
async def create_asset(db: AsyncSession, asset_in: AssetCreate, current_user_tab_id: Optional[str]) -> Asset:
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
        # performed_by=current_user_tab_id,
        performed_by=current_user_tab_id,
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
        model_id: Optional[int] = None,
        deleted: bool = False
) -> Sequence[Any]:
    """
    Получает список активов с применением фильтров и пагинацией.
    Загружает связи для корректной работы фильтрации по правам.
    """
    query = select(Asset).options(
        # Для type_asset
        selectinload(Asset.model)
        .selectinload(AssetModel.asset_class)
        .selectinload(AssetClass.asset_type),

        # === ДОБАВЬ ЭТИ СТРОКИ для работы *_name в списках ===
        selectinload(Asset.parent),        # Обязательно, т.к. в модели lazy="selectin"
        selectinload(Asset.software),      # Для software_name и software_office_type
        selectinload(Asset.warehouse_obj), # На всякий случай
        selectinload(Asset.workshop),      # Чтобы не падало в роутерах каталога
    )

    # Фильтры
    if asset_status:
        query = query.where(Asset.asset_status == asset_status)
    if model_id:
        query = query.where(Asset.model_id == model_id)

    # Пагинация
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    res = result.scalars().all()
    print(f"{res=}")
    return res

async def get_asset_by_id(db: AsyncSession, asset_id: int) -> Optional[Asset]:
    """
    Получает полный объект актива со ВСЕМИ связями для детального ответа.
    """
    result = await db.execute(
        select(Asset)
        .where(Asset.asset_id == asset_id)
        .options(
            selectinload(Asset.model).selectinload(AssetModel.asset_class),    # Загрузка модели актива (relationship)
            selectinload(Asset.model).selectinload(AssetModel.creator),
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
            selectinload(Asset.workshop),  # Загрузка цеха
        )
    )
    return result.scalar_one_or_none()

# async def update_asset(db: AsyncSession, asset_id: int, asset_data: AssetUpdate, current_user_id: Optional[int] = None) -> Optional[Asset]:
#     """
#     Обновляет поля актива и записывает историю изменений.
#     """
#     # Получаем актив
#     asset = await get_active_asset(db, asset_id)
#     if not asset:
#         return None
#
#     # Фиксируем старые значения ДО обновления
#     old_values = {}
#
#     # Собираем только те поля, которые пришли в запросе на обновление (exclude_unset=True)
#     update_data = asset_data.model_dump(exclude_unset=True)
#
#     for key in update_data.keys():
#         if hasattr(asset, key):
#             # Сохраняем старое значение
#             old_val = getattr(asset, key)
#             old_values[key] = old_val
#
#     # Применяем обновления
#     for key, value in update_data.items():
#         setattr(asset, key, value)
#
#     # Обновляем timestamp вручную, если он не обновляется автоматически onupdate
#     asset.updated_at = datetime.utcnow()
#
#     await db.commit()
#
#     # Логируем операцию UPDATE
#     if old_values: # Пишем лог только если что-то реально изменилось
#         try:
#             await create_operation_log(
#                 db=db,
#                 asset_id=asset_id,
#                 operation_type="UPDATE",
#                 performed_by=current_user_id,
#                 old_values=old_values,
#                 new_values=update_data,
#                 comment="Обновление данных актива",
#                 inventory_id_snapshot=asset.inventory_id,
#                 name_snapshot=asset.name
#             )
#         except Exception as e:
#             # Если логирование упало, мы не должны ломать основное обновление,
#             # но в продакшене лучше залогировать ошибку в stderr/logger
#             print(f"Error logging operation: {e}")
#
#     # Возвращаем обновленный актив с полными связями
#     # Важно перегрузить его через get_asset_by_id, чтобы избежать MissingGreenlet при сериализации связей
#     updated_asset_full = await get_asset_by_id(db, asset_id)
#
#     return updated_asset_full

async def update_asset(db: AsyncSession, asset_id: int, asset_data: AssetUpdate, user_tab_id: str):
    result = await db.execute(select(Asset).where(Asset.asset_id == asset_id))
    asset = result.scalars().first()
    if not asset:
        return None

    # Получаем список реальных колонок модели Asset
    valid_columns = set(Asset.__table__.columns.keys())

    # Берём только те поля, которые были реально изменены (exclude_unset=True)
    # и которые существуют как колонки в модели
    update_data = asset_data.model_dump(exclude_unset=True, exclude_none=True)

    for key, value in update_data.items():
        if key in valid_columns:
            setattr(asset, key, value)
        # Поля, которых нет в valid_columns (class_id, model_name и т.д.) — просто игнорируем

    asset.updated_by = user_tab_id  # если есть такое поле
    await db.commit()
    await db.refresh(asset)
    return asset

async def update_asset_with_users(
        db: AsyncSession,
        asset_id: int,
        asset_data: AssetUpdateWithUsers,
        current_user_tab_id: Optional[str] = None
) -> Optional[Asset]:
    """
    Обновляет актив и управляет привязкой пользователей через asset_catalog.
    1. Обновляет поля актива
    2. Удаляет старые записи asset_catalog для этого актива
    3. Создаёт новые записи asset_catalog для выбранных пользователей
    """
    # === 1. Получаем актив ===
    asset = await get_active_asset(db, asset_id)
    if not asset:
        return None

    # === 2. Фиксируем старые значения для истории ===
    old_values = {}
    update_data = asset_data.model_dump(exclude_unset=True, exclude={"users"})

    for key in update_data.keys():
        if hasattr(asset, key):
            old_val = getattr(asset, key)
            old_values[key] = old_val

    # === 3. Обновляем поля актива ===
    valid_columns = set(Asset.__table__.columns.keys())
    for key, value in update_data.items():
        if key in valid_columns:
            setattr(asset, key, value)

    # === 4. Удаляем старые записи из asset_catalog ===
    await db.execute(
        delete(AssetCatalog).where(AssetCatalog.asset_id == asset_id)
    )

    # === 5. Создаём новые записи asset_catalog для выбранных пользователей ===
    for user in asset_data.users:
        if user.selected:
            catalog_entry = AssetCatalog(
                asset_id=asset_id,
                # owner_id=user.user_id,
                owner_id=user.user_tab_id,
                # created_by=current_user_id or user.user_id
                created_by=current_user_tab_id or user.user_tab_id
            )
            db.add(catalog_entry)

    # === 6. Коммитим транзакцию ===
    try:
        await db.commit()
        await db.refresh(asset)

        # === 7. Логируем операцию ===
        # if current_user_id:
        if current_user_tab_id:
            await create_operation_log(
                db=db,
                asset_id=asset_id,
                operation_type="update",
                performed_by=current_user_tab_id,
                old_values=old_values,
                new_values=update_data,
                inventory_id_snapshot=asset_data.inventory_id,
                name_snapshot=asset_data.name
            )

        return asset
    except Exception as e:
        await db.rollback()
        raise

async def hard_delete_asset(db: AsyncSession, asset_id: int, current_user_tab_id: Optional[str] = None) -> bool:
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
                # performed_by=current_user_id,
                performed_by=current_user_tab_id,
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

async def get_all_asset_children_recursive(
        db: AsyncSession,
        asset_id: int,
        max_depth: Optional[int] = None
) -> List[Asset]:
    """
    Получает всех дочерних активов рекурсивно через CTE.
    Возвращает объекты Asset с загруженными связями для проверки прав.
    """
    # Проверяем существование родителя
    parent = await db.get(Asset, asset_id)
    if not parent:
        return []

    # CTE-запрос для получения всех детей (только активные)
    base_query = """
                 WITH RECURSIVE asset_tree AS (
                     -- Базовый случай: прямые дети
                     SELECT asset_id, parent_id, 1 AS depth
                     FROM assets
                     WHERE parent_id = :root_id IS NULL

                     UNION ALL

                     -- Рекурсия: дети детей
                     SELECT a.asset_id, a.parent_id, at.depth + 1
                     FROM assets a
                              INNER JOIN asset_tree at ON a.parent_id = at.asset_id
                 """

    if max_depth:
        base_query += " AND at.depth < :max_depth"

    base_query += """
        )
        SELECT asset_id FROM asset_tree ORDER BY depth, asset_id
    """

    params = {"root_id": asset_id}
    if max_depth:
        params["max_depth"] = max_depth

    # Выполняем CTE, получаем список ID детей
    result = await db.execute(text(base_query), params)
    child_ids = [row[0] for row in result.fetchall()]

    if not child_ids:
        return []

    # Загружаем объекты с необходимыми связями для проверки прав
    result = await db.execute(
        select(Asset)
        .where(Asset.asset_id.in_(child_ids))
        .options(
            # Загружаем цепочку: model → asset_class → asset_type
            selectinload(Asset.model)
            .selectinload(AssetModel.asset_class)
            .selectinload(AssetClass.asset_type)
        )
    )

    # Возвращаем в порядке из CTE (по глубине)
    assets_map = {a.asset_id: a for a in result.scalars().all()}
    return [assets_map[cid] for cid in child_ids if cid in assets_map]


##############    Для карты активов    ##############
async def get_asset_positions(db: AsyncSession, asset_id: int) -> Sequence[Any]:
    """
    Получение всех позиций актива на картах (история + текущая).
    """
    result = await db.execute(
        select(AssetPosition)
        .where(AssetPosition.asset_id == asset_id)
        .order_by(AssetPosition.created_at.desc())
    )
    return result.scalars().all()

async def get_active_asset_position(db: AsyncSession, asset_id: int) -> Optional[AssetPosition]:
    """
    Получение текущей (активной) позиции актива.
    """
    result = await db.execute(
        select(AssetPosition)
        .where(AssetPosition.asset_id == asset_id, AssetPosition.is_active == True)
    )
    return result.scalar_one_or_none()
##############  ////  Для карты активов  ////  ##############

async def search_assets(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        name: Optional[str] = None,
        type_id: Optional[int] = None,
        class_id: Optional[int] = None,
        model_id: Optional[int] = None,
        model_name: Optional[str] = None,
        class_name: Optional[str] = None,
        type_asset_en_name: Optional[str] = None,
        type_asset_name: Optional[str] = None
) -> Sequence[Asset]:
    """
    Поиск активов по множеству опциональных параметров.
    Все параметры комбинируются через AND.
    Текстовые параметры ищутся через ILIKE (частичное совпадение, без учета регистра).
    ID параметры ищутся через точное совпадение.
    """
    query = select(Asset).options(
        selectinload(Asset.model).selectinload(AssetModel.asset_class).selectinload(AssetClass.asset_type),
        selectinload(Asset.parent),
        selectinload(Asset.software),
        selectinload(Asset.warehouse_obj),
        selectinload(Asset.manufacturer),
        selectinload(Asset.vendor)
    )

    # Фильтр по name актива
    if name:
        query = query.where(Asset.name.ilike(f"%{name}%"))

    # Фильтр по model_id (точное совпадение)
    if model_id is not None:
        query = query.where(Asset.model_id == model_id)

    # Фильтр по model_name (частичное совпадение)
    if model_name:
        query = query.where(Asset.model.has(AssetModel.model_name.ilike(f"%{model_name}%")))

    # Фильтр по class_id (точное совпадение)
    if class_id is not None:
        query = query.where(
            Asset.model.has(AssetModel.asset_class.has(AssetClass.class_id == class_id))
        )

    # Фильтр по class_name (частичное совпадение)
    if class_name:
        query = query.where(
            Asset.model.has(AssetModel.asset_class.has(AssetClass.class_name.ilike(f"%{class_name}%")))
        )

    # Фильтр по type_id (точное совпадение)
    if type_id is not None:
        query = query.where(
            Asset.model.has(
                AssetModel.asset_class.has(
                    AssetClass.asset_type.has(AssetType.asset_type_id == type_id)
                )
            )
        )

    # Фильтр по type_asset_en_name (частичное совпадение)
    if type_asset_en_name:
        query = query.where(
            Asset.model.has(
                AssetModel.asset_class.has(
                    AssetClass.asset_type.has(AssetType.en_name.ilike(f"%{type_asset_en_name}%"))
                )
            )
        )

    # Фильтр по type_asset_name (частичное совпадение)
    if type_asset_name:
        query = query.where(
            Asset.model.has(
                AssetModel.asset_class.has(
                    AssetClass.asset_type.has(AssetType.name.ilike(f"%{type_asset_name}%"))
                )
            )
        )

    # Пагинация
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

async def create_asset_for_mu(
        db: AsyncSession,
        name: str,
        inventory_id: str,
        serial_number: str,
        asset_status: str,
        comment: Optional[str],
        model_id: Optional[int],
        type_asset_id: Optional[int],
        warehouse_id: Optional[int],
        parent_id: Optional[int],
        software_id: Optional[int],
        manufacturer_id: Optional[int],
        vendor_id: Optional[int]
) -> Asset:
    """Создание нового актива"""
    asset = Asset(
        name=name,
        inventory_id=inventory_id,
        serial_number=serial_number,
        asset_status=asset_status,
        comment=comment,
        model_id=model_id,
        type_asset_id=type_asset_id,
        warehouse_id=warehouse_id,
        parent_id=parent_id,
        software_id=software_id,
        manufacturer_id=manufacturer_id,
        vendor_id=vendor_id
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset