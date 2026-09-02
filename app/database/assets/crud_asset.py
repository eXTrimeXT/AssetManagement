from datetime import date
from typing import Optional, Sequence, List, Any, Tuple, Dict
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.schemas.assets.AssetSchemas import AssetCreate, AssetUpdate
from app.models.assets.Asset import Asset
from app.models.assets import AssetType
from app.models.assets.AssetAssignment import AssetAssignment
from app.models.assets.AssetStatus import AssetStatus
from app.models.map_assets.AssetPosition import AssetPosition
from app.database.assets.crud_asset_history import compare_and_save_changes
from app.database.crud_notifications import notify_assigned_user, notify_assigned_responsible, notify_unassigned_user, \
    notify_unassigned_responsible

# Импорты для оптимизации запроса связки актива и пользователя
from app.schemas.zup import PositionResponse
from app.schemas.assets.AssetAssignmentSchemas import AssetUserFullResponse
from app.database.zup import get_position_by_guid
from app.database.zup.crud_zup_departments import get_hierarchy_departments


async def create_asset(db: AsyncSession, data: AssetCreate, employee_id: str) -> Asset | None:
    # ИСКЛЮЧАЕМ asset_status, чтобы не передать строку в relationship
    asset_data = data.model_dump(exclude={"users", "responsible_users", "asset_status"})

    # Создаем актив
    db_obj = Asset(**asset_data, created_by=employee_id, updated_by=employee_id)

    # === ОБРАБОТКА СТАТУСА ===
    if data.asset_status:
        result = await db.execute(
            select(AssetStatus).where(AssetStatus.status == data.asset_status)
        )
        status_obj = result.scalars().first()
        if status_obj:
            db_obj.asset_status_id = status_obj.id
    # =========================

    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)

    # Синхронизация привязок пользователей, если они переданы
    if data.users is not None or data.responsible_users is not None:
        await _sync_asset_users(db, db_obj.asset_id, data.users or [], data.responsible_users or [], employee_id)
        await db.commit()

    # === НОВОЕ: Создание локации на карте ===
    if data.location is not None:
        await _sync_asset_location(db, db_obj.asset_id, data.location, employee_id)

    # Возвращаем актив с загруженными связями
    return await get_asset_by_id(db, db_obj.asset_id)

async def get_asset_by_id(db: AsyncSession, asset_id: int) -> Optional[Asset]:
    result = await db.execute(
        select(Asset)
        .where(Asset.asset_id == asset_id)
        .options(
            selectinload(Asset.asset_type),
            selectinload(Asset.asset_status),
            selectinload(Asset.model),
            selectinload(Asset.parent).options(
                selectinload(Asset.asset_type),
                # === загрузка asset_status для родителя ===
                selectinload(Asset.asset_status),
                selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
                selectinload(Asset.assignments).options(
                    selectinload(AssetAssignment.employee)
                )
            ),
            # загрузка asset_positions для основного актива
            selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
            selectinload(Asset.assignments).options(
                selectinload(AssetAssignment.employee)
            ),
            selectinload(Asset.creator),
            selectinload(Asset.updater),
        )
    )
    return result.scalar_one_or_none()

def _apply_assets_filters(
        query, name, inventory_id, serial_number, asset_status,
        model_id, asset_type_id, parent_id,
        allowed_type_en_names
):
    if name:
        query = query.where(Asset.name.ilike(f"%{name}%"))
    if inventory_id:
        # query = query.where(Asset.inventory_id == inventory_id)
        query = query.where(Asset.inventory_id.ilike(f"%{inventory_id}%"))
    if serial_number:
        # query = query.where(Asset.serial_number == serial_number)
        query = query.where(Asset.serial_number.ilike(f"%{serial_number}%"))
    # if asset_status:
    #     query = query.where(Asset.asset_status == asset_status)
    if asset_status:
        query = query.join(AssetStatus, Asset.asset_status_id == AssetStatus.id)
        query = query.where(AssetStatus.status == asset_status)
    if model_id is not None:
        query = query.where(Asset.model_id == model_id)
    if asset_type_id is not None:
        query = query.where(Asset.asset_type_id == asset_type_id)
    if parent_id is not None:
        query = query.where(Asset.parent_id == parent_id)

    if allowed_type_en_names is not None:
        query = (
            query.outerjoin(Asset.asset_type)
            .where(AssetType.en_name.in_(allowed_type_en_names))
        )

    return query

async def get_assets_count(
        db: AsyncSession,
        name: Optional[str] = None,
        inventory_id: Optional[str] = None,
        serial_number: Optional[str] = None,
        asset_status: Optional[str] = None,
        model_id: Optional[int] = None,
        asset_type_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        allowed_type_en_names: Optional[List[str]] = None,
) -> int:
    if allowed_type_en_names is not None and len(allowed_type_en_names) == 0:
        return 0

    query = select(func.count(Asset.asset_id)).select_from(Asset)
    query = _apply_assets_filters(
        query, name, inventory_id, serial_number, asset_status,
        model_id, asset_type_id, parent_id,
        allowed_type_en_names
    )
    result = await db.execute(query)
    return result.scalar_one()

async def get_assets_list(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 50,
        name: Optional[str] = None,
        inventory_id: Optional[str] = None,
        serial_number: Optional[str] = None,
        asset_status: Optional[str] = None,
        model_id: Optional[int] = None,
        asset_type_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        allowed_type_en_names: Optional[List[str]] = None,
) -> Tuple[Sequence[Asset], int]:
    if allowed_type_en_names is not None and len(allowed_type_en_names) == 0:
        return [], 0

    total = await get_assets_count(
        db, name, inventory_id, serial_number, asset_status,
        model_id, asset_type_id, parent_id, allowed_type_en_names
    )

    skip = (page - 1) * page_size

    query = select(Asset).options(
        selectinload(Asset.asset_type),
        selectinload(Asset.asset_status),
        selectinload(Asset.model),
        selectinload(Asset.parent).options(
            selectinload(Asset.asset_type),
            selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
        ),
        selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
        selectinload(Asset.assignments).options(
            selectinload(AssetAssignment.employee)
        ),
    )

    query = _apply_assets_filters(
        query, name, inventory_id, serial_number, asset_status,
        model_id, asset_type_id, parent_id, allowed_type_en_names
    )

    query = query.order_by(Asset.asset_id)
    query = query.offset(skip).limit(page_size)

    result = await db.execute(query)
    assets = result.scalars().all()

    return assets, total

async def update_asset(db: AsyncSession, asset_id: int, data: AssetUpdate, employee_id: str) -> Optional[Asset]:
    obj = await get_asset_by_id(db, asset_id)
    if not obj:
        return None

    # === Получаем старую локацию для истории ===
    old_location_data = None
    for pos in (obj.asset_positions or []):
        if pos.is_active:
            old_location_data = {
                "workshop_id": pos.workshop_id,
                "place": pos.place,
                "level": pos.level,
                "x": pos.x,
                "y": pos.y,
            }
            break

    # Сохраняем старые значения для истории
    old_data = {
        'name': obj.name,
        'inventory_id': obj.inventory_id,
        'serial_number': obj.serial_number,
        'comment': obj.comment,
        'date_issue': obj.date_issue,
        'date_purchasing': obj.date_purchasing,
        'model_id': obj.model_id,
        'model_name': obj.model_name,
        'asset_type_id': obj.asset_type_id,
        'parent_id': obj.parent_id,
        'location': str(old_location_data) if old_location_data else None,
        'asset_status_id': obj.asset_status_id,
        'parent_name': obj.parent_name,
        'manufacturer_name': obj.manufacturer_name,
        'vendor_name': obj.vendor_name,
        'os_name': obj.os_name
    }

    # ИСПРАВЛЕНО: asset_status_id обрабатывается как обычное поле, без специальной логики
    # Строковое поле asset_status полностью игнорируется
    update_data = data.model_dump(
        exclude_unset=True,
        exclude={"users", "responsible_users", "asset_status", "location"}
    )

    # Обновляем ВСЕ поля актива через ЕДИНУЮ общую логику
    for key, value in update_data.items():
        setattr(obj, key, value)
    obj.updated_by = employee_id

    # === ОБРАБОТКА ЛОКАЦИИ НА КАРТЕ ===
    new_location_data = None
    if "location" in data.model_fields_set and data.location is not None:
        new_location_data = await _sync_asset_location(db, asset_id, data.location, employee_id)

    # === СОХРАНЕНИЕ ИСТОРИИ ИЗМЕНЕНИЙ ===
    new_data = {
        'name': obj.name,
        'inventory_id': obj.inventory_id,
        'serial_number': obj.serial_number,
        'comment': obj.comment,
        'date_issue': obj.date_issue,
        'date_purchasing': obj.date_purchasing,
        'model_id': obj.model_id,
        'model_name': obj.model_name,
        'asset_type_id': obj.asset_type_id,
        'parent_id': obj.parent_id,
        'location': str(new_location_data) if new_location_data else (
            str(old_location_data) if old_location_data else None
        ),
        'asset_status_id': obj.asset_status_id,
        'parent_name': obj.parent_name,
        'manufacturer_name': obj.manufacturer_name,
        'vendor_name': obj.vendor_name,
        'os_name': obj.os_name
    }

    await compare_and_save_changes(
        db=db,
        asset_id=asset_id,
        old_data=old_data,
        new_data=new_data,
        changed_by=employee_id
    )

    # Синхронизация привязок пользователей
    if data.users is not None or data.responsible_users is not None:
        await _sync_asset_users(db, asset_id, data.users or [], data.responsible_users or [], employee_id)

    await db.commit()
    return await get_asset_by_id(db, asset_id)

def _enrich_users_from_cache(
        users_data: list,
        dept_hierarchy_cache: Dict[str, Any],
        pos_cache: Dict[str, Any]
) -> list:
    """Обогащает данные пользователей, используя кэш иерархий и должностей (без запросов к БД)."""
    enriched = []
    for user in users_data:
        user_dict = user.model_dump() if hasattr(user, 'model_dump') else user

        # 1. Обогащаем иерархией подразделения из кэша
        dept_guid = user_dict.get("department_guid")
        if dept_guid and dept_guid in dept_hierarchy_cache:
            hierarchy = dept_hierarchy_cache[dept_guid]
            if hierarchy:
                user_dict["society"] = hierarchy.society
                user_dict["department"] = hierarchy.department
                user_dict["division"] = hierarchy.division
                user_dict["group"] = hierarchy.group

        # 2. Обогащаем должностью из кэша
        pos_guid = user_dict.get("position_guid")
        if pos_guid and pos_guid in pos_cache:
            pos = pos_cache[pos_guid]
            if pos:
                user_dict["position"] = PositionResponse.model_validate(pos)

        enriched.append(AssetUserFullResponse(**user_dict))

    return enriched


async def bulk_enrich_assets(db: AsyncSession, assets: list) -> None:
    """
    Оптимизированное обогащение с кэшированием.
    Решает проблему N+1, вызывая тяжелые функции только для УНИКАЛЬНЫХ guid.
    """
    # 1. Собираем уникальные GUID'ы со всех пользователей всех активов
    unique_dept_guids = set()
    unique_pos_guids = set()

    for asset in assets:
        for user in (asset.users or []) + (asset.responsible_users or []):
            user_dict = user.model_dump() if hasattr(user, 'model_dump') else user
            if user_dict.get("department_guid"):
                unique_dept_guids.add(user_dict["department_guid"])
            if user_dict.get("position_guid"):
                unique_pos_guids.add(user_dict["position_guid"])

    # 2. Кэшируем иерархии подразделений (вызов тяжелой функции только для уникальных GUID)
    dept_hierarchy_cache = {}
    for guid in unique_dept_guids:
        hierarchy = await get_hierarchy_departments(db, guid)
        dept_hierarchy_cache[guid] = hierarchy

    # 3. Кэшируем должности
    pos_cache = {}
    for guid in unique_pos_guids:
        position = await get_position_by_guid(db, guid)
        pos_cache[guid] = position

    # 4. Обогащаем данные в памяти, используя готовые кэши
    for asset in assets:
        if asset.users:
            asset.users = _enrich_users_from_cache(asset.users, dept_hierarchy_cache, pos_cache)
        if asset.responsible_users:
            asset.responsible_users = _enrich_users_from_cache(asset.responsible_users, dept_hierarchy_cache, pos_cache)

async def _sync_asset_users(
        db: AsyncSession,
        asset_id: int,
        users: list,
        responsible_users: list,
        assigned_by: str,
) -> None:
    """
    Синхронизация привязок пользователей к активу.

    Логика:
    - Новые пользователи (которых нет в активных привязках) → уведомление
    - Существующие пользователи (уже привязанные) → БЕЗ уведомления
    - Отвязанные пользователи (есть в БД, но нет в запросе) → уведомление об отвязке
    """
    requested_user_ids = {user.employee_id for user in (users or [])}
    requested_responsible_ids = {user.employee_id for user in (responsible_users or [])}

    # Получаем все активные привязки
    result = await db.execute(
        select(AssetAssignment).where(
            AssetAssignment.asset_id == asset_id,
            AssetAssignment.end_date.is_(None)
        )
    )
    active_assignments = result.scalars().all()

    # Мапы для быстрого поиска
    active_user_ids = {
        a.employee_id for a in active_assignments
        if a.assignment_type == "user"
    }
    active_responsible_ids = {
        a.employee_id for a in active_assignments
        if a.assignment_type == "responsible"
    }

    # === НОВЫЕ обычные пользователи (привязка + уведомление) ===
    for employee_id in requested_user_ids:
        if employee_id in active_user_ids:
            # Уже привязан — пропускаем без уведомления
            continue

        new_assignment = AssetAssignment(
            asset_id=asset_id,
            employee_id=employee_id,
            assignment_type="user",
            start_date=date.today(),
            end_date=None,
            assigned_by=assigned_by
        )
        db.add(new_assignment)

        # Уведомление только для НОВОГО пользователя
        await notify_assigned_user(
            db=db,
            employee_id=employee_id,
            asset_id=asset_id,
            initiator_id=assigned_by,
        )

    # === НОВЫЕ ответственные пользователи (привязка + уведомление) ===
    for employee_id in requested_responsible_ids:
        if employee_id in active_responsible_ids:
            # Уже привязан — пропускаем без уведомления
            continue

        new_assignment = AssetAssignment(
            asset_id=asset_id,
            employee_id=employee_id,
            assignment_type="responsible",
            start_date=date.today(),
            end_date=None,
            assigned_by=assigned_by
        )
        db.add(new_assignment)

        # Уведомление только для НОВОГО ответственного
        await notify_assigned_responsible(
            db=db,
            employee_id=employee_id,
            asset_id=asset_id,
            initiator_id=assigned_by,
        )

    # === Отвязка пользователей (которых нет в запросе) ===
    for assignment in active_assignments:
        should_unassign = False

        if assignment.assignment_type == "user":
            should_unassign = assignment.employee_id not in requested_user_ids
        elif assignment.assignment_type == "responsible":
            should_unassign = assignment.employee_id not in requested_responsible_ids

        if should_unassign:
            assignment.end_date = date.today()

            # Уведомление об отвязке
            if assignment.assignment_type == "user":
                await notify_unassigned_user(
                    db=db,
                    employee_id=assignment.employee_id,
                    asset_id=asset_id,
                    initiator_id=assigned_by,
                )
            else:
                await notify_unassigned_responsible(
                    db=db,
                    employee_id=assignment.employee_id,
                    asset_id=asset_id,
                    initiator_id=assigned_by,
                )

async def _sync_asset_location(
        db: AsyncSession,
        asset_id: int,
        location_data,  # AssetLocationUpdate
        assigned_by: str
) -> dict:
    """
    Синхронизация позиции актива на карте.
    - Деактивирует все существующие позиции (is_active = False)
    - Создаёт новую активную позицию
    """
    # Деактивируем все существующие позиции для этого актива
    result = await db.execute(
        select(AssetPosition).where(
            AssetPosition.asset_id == asset_id,
            AssetPosition.is_active == True
        )
    )
    existing_positions = result.scalars().all()
    for pos in existing_positions:
        pos.is_active = False

    # Создаём новую активную позицию
    new_position = AssetPosition(
        asset_id=asset_id,
        workshop_id=location_data.workshop_id,
        place=location_data.place,
        level=location_data.level,
        x=location_data.x,
        y=location_data.y,
        rotation=location_data.rotation if hasattr(location_data, 'rotation') else 0,
        scale=location_data.scale if hasattr(location_data, 'scale') else 100,
        is_active=True,
    )
    db.add(new_position)
    await db.flush()  # Получаем id без commit

    return {
        "workshop_id": new_position.workshop_id,
        "place": new_position.place,
        "level": new_position.level,
        "x": new_position.x,
        "y": new_position.y,
    }

async def delete_asset(db: AsyncSession, asset_id: int) -> bool:
    obj = await get_asset_by_id(db, asset_id)
    if not obj:
        return False

    await db.delete(obj)
    await db.commit()
    return True

async def get_asset_children(db: AsyncSession, asset_id: int) -> Sequence[Any]:
    result = await db.execute(
        select(Asset)
        .options(
            selectinload(Asset.asset_type),
            # selectinload(Asset.model).options(
            #     selectinload(AssetModel.asset_type)
            # ),
            selectinload(Asset.parent)
        )
        .where(Asset.parent_id == asset_id)
    )
    return result.scalars().all()

async def get_active_assets_by_employee(db: AsyncSession, employee_id: str) -> Sequence[Asset]:
    """Получить все текущие (активные) активы сотрудника."""
    query = (
        select(Asset)
        .join(AssetAssignment, Asset.asset_id == AssetAssignment.asset_id)
        .where(
            AssetAssignment.employee_id == employee_id,
            AssetAssignment.end_date.is_(None)
        )
        .options(
            selectinload(Asset.asset_type),
            selectinload(Asset.asset_status),
            selectinload(Asset.model),
            selectinload(Asset.parent).options(
                selectinload(Asset.asset_type),
                selectinload(Asset.asset_status),
                selectinload(Asset.model),
                # === загрузка позиций и workshop для родителя ===
                selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
                selectinload(Asset.assignments).options(
                    selectinload(AssetAssignment.employee)
                ),
            ),
            # === загрузка позиций и workshop для основного актива ===
            selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
            selectinload(Asset.assignments).options(selectinload(AssetAssignment.employee)),
            selectinload(Asset.creator),
            selectinload(Asset.updater),
        )
        .distinct()
    )
    result = await db.execute(query)
    return result.scalars().all()