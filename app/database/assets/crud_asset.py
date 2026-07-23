from datetime import date
from typing import Optional, Sequence, List, Any, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.assets.Asset import Asset
# from app.models.assets.asset_model import AssetModel
from app.schemas.assets.AssetSchemas import AssetCreate, AssetUpdate
from app.models.assets import AssetType
from app.models.assets.AssetAssignment import AssetAssignment


# async def create_asset(db: AsyncSession, data: AssetCreate, employee_id: str) -> Asset | None:
#     db_obj = Asset(**data.model_dump(), created_by=employee_id, updated_by=employee_id)
#     db.add(db_obj)
#     await db.commit()
#     await db.refresh(db_obj)
#     return await get_asset_by_id(db, db_obj.asset_id)

async def create_asset(db: AsyncSession, data: AssetCreate, employee_id: str) -> Asset | None:
    # Исключаем users из model_dump, так как у модели Asset нет такого поля
    asset_data = data.model_dump(exclude={"users"})

    # Создаем актив
    db_obj = Asset(**asset_data, created_by=employee_id, updated_by=employee_id)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)

    # Синхронизация привязок пользователей, если они переданы
    if data.users is not None:
        await _sync_asset_users(db, db_obj.asset_id, data.users, employee_id)
        await db.commit()

    # Возвращаем актив с загруженными связями
    return await get_asset_by_id(db, db_obj.asset_id)

async def get_asset_by_id(db: AsyncSession, asset_id: int) -> Optional[Asset]:
    result = await db.execute(
        select(Asset)
        .where(Asset.asset_id == asset_id)
        .options(
            selectinload(Asset.asset_type),
            selectinload(Asset.model),
            selectinload(Asset.parent).options(
                selectinload(Asset.asset_type),
                selectinload(Asset.location),
                selectinload(Asset.model),
                # === Загружаем assignments И employee для родителя ===
                selectinload(Asset.assignments).options(
                    selectinload(AssetAssignment.employee)
                )
            ),
            selectinload(Asset.location),
            selectinload(Asset.assignments).options(
                selectinload(AssetAssignment.employee)
            ),
            selectinload(Asset.preparer),
            selectinload(Asset.checker),
            selectinload(Asset.creator),
            selectinload(Asset.updater),
        )
    )
    return result.scalar_one_or_none()

def _apply_assets_filters(
        query, name, inventory_id, serial_number, asset_status,
        model_id, asset_type_id, parent_id, location_id, allowed_type_en_names
):
    if name:
        query = query.where(Asset.name.ilike(f"%{name}%"))
    if inventory_id:
        # query = query.where(Asset.inventory_id == inventory_id)
        query = query.where(Asset.inventory_id.ilike(f"%{inventory_id}%"))
    if serial_number:
        # query = query.where(Asset.serial_number == serial_number)
        query = query.where(Asset.serial_number.ilike(f"%{serial_number}%"))
    if asset_status:
        query = query.where(Asset.asset_status == asset_status)
    if model_id is not None:
        query = query.where(Asset.model_id == model_id)
    if asset_type_id is not None:
        query = query.where(Asset.asset_type_id == asset_type_id)
    if parent_id is not None:
        query = query.where(Asset.parent_id == parent_id)
    if location_id is not None:
        query = query.where(Asset.location_id == location_id)

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
        location_id: Optional[int] = None,
        allowed_type_en_names: Optional[List[str]] = None,
) -> int:
    if allowed_type_en_names is not None and len(allowed_type_en_names) == 0:
        return 0

    query = select(func.count(Asset.asset_id)).select_from(Asset)
    query = _apply_assets_filters(
        query, name, inventory_id, serial_number, asset_status,
        model_id, asset_type_id, parent_id, location_id, allowed_type_en_names
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
        location_id: Optional[int] = None,
        allowed_type_en_names: Optional[List[str]] = None,
) -> Tuple[Sequence[Asset], int]:
    if allowed_type_en_names is not None and len(allowed_type_en_names) == 0:
        return [], 0

    total = await get_assets_count(
        db, name, inventory_id, serial_number, asset_status,
        model_id, asset_type_id, parent_id, location_id, allowed_type_en_names
    )

    skip = (page - 1) * page_size

    query = select(Asset).options(
        selectinload(Asset.asset_type),
        selectinload(Asset.model),
        selectinload(Asset.parent).options(
            selectinload(Asset.asset_type),
            selectinload(Asset.location),
            selectinload(Asset.model),
            # === Загружаем assignments И employee для родителя ===
            selectinload(Asset.assignments).options(
                selectinload(AssetAssignment.employee)
            )
        ),
        selectinload(Asset.assignments).options(
            selectinload(AssetAssignment.employee)
        ),
        selectinload(Asset.location),
    )

    query = _apply_assets_filters(
        query, name, inventory_id, serial_number, asset_status,
        model_id, asset_type_id, parent_id, location_id, allowed_type_en_names
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

    # Извлекаем users отдельно, чтобы не передавать в setattr
    update_data = data.model_dump(exclude_unset=True, exclude={"users"})

    # Обновляем поля актива
    for key, value in update_data.items():
        setattr(obj, key, value)
    obj.updated_by = employee_id

    # Синхронизация привязок пользователей
    if data.users is not None:
        await _sync_asset_users(db, asset_id, data.users, employee_id)

    await db.commit()
    return await get_asset_by_id(db, asset_id)

async def _sync_asset_users(
        db: AsyncSession,
        asset_id: int,
        users: list,
        assigned_by: str
) -> None:
    """
    Синхронизация привязок пользователей к активу.
    - Пользователи из массива users привязываются
    - Все остальные активные привязки закрываются
    """
    # Получаем список employee_id из запроса
    requested_employee_ids = {user.employee_id for user in users}

    # Получаем все активные привязки для этого актива
    result = await db.execute(
        select(AssetAssignment).where(
            AssetAssignment.asset_id == asset_id,
            AssetAssignment.end_date.is_(None)
        )
    )
    active_assignments = result.scalars().all()
    active_employee_ids = {assignment.employee_id for assignment in active_assignments}

    # Привязываем новых пользователей
    for employee_id in requested_employee_ids:
        if employee_id not in active_employee_ids:
            new_assignment = AssetAssignment(
                asset_id=asset_id,
                employee_id=employee_id,
                start_date=date.today(),
                end_date=None,
                assigned_by=assigned_by
            )
            db.add(new_assignment)

    # Отвязываем пользователей, которых нет в запросе
    for assignment in active_assignments:
        if assignment.employee_id not in requested_employee_ids:
            assignment.end_date = date.today()

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
            selectinload(Asset.model),  # Добавлено
            selectinload(Asset.parent).options(
                selectinload(Asset.asset_type),  # Добавлено
                selectinload(Asset.location),
                selectinload(Asset.model)
            ),
            selectinload(Asset.location),
            selectinload(Asset.assignments).options(selectinload(AssetAssignment.employee)),
            selectinload(Asset.preparer),
            selectinload(Asset.checker),
            selectinload(Asset.creator),
            selectinload(Asset.updater),
        )
        .distinct()
    )
    result = await db.execute(query)
    return result.scalars().all()