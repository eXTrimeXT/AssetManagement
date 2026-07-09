from datetime import date
from typing import Optional, Sequence, List, Any, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.assets.asset import Asset
# from app.models.assets.asset_model import AssetModel
from app.schemas.assets.asset import AssetCreate, AssetUpdate
from app.models.assets import AssetType
from app.models.assets.asset_assignment import AssetAssignment


async def create_asset(db: AsyncSession, data: AssetCreate, employee_id: str) -> Asset | None:
    db_obj = Asset(**data.model_dump(), created_by=employee_id, updated_by=employee_id)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return await get_asset_by_id(db, db_obj.asset_id)

async def get_asset_by_id(db: AsyncSession, asset_id: int) -> Optional[Asset]:
    result = await db.execute(
        select(Asset)
        .options(
            selectinload(Asset.asset_type),
            # selectinload(Asset.model).options(
            #     selectinload(AssetModel.asset_type)
            # ),
            selectinload(Asset.parent).options(selectinload(Asset.assignments),),
            selectinload(Asset.location),
            selectinload(Asset.assignments).options(
                selectinload(AssetAssignment.employee)
            ),
            selectinload(Asset.preparer),
            selectinload(Asset.checker),
            selectinload(Asset.creator),
            selectinload(Asset.updater)
        )
        .where(Asset.asset_id == asset_id)
    )
    return result.scalar_one_or_none()

def _apply_assets_filters(
        query, name, inventory_id, serial_number, asset_status,
        model_id, asset_type_id, parent_id, location_id, allowed_type_en_names
):
    if name:
        query = query.where(Asset.name.ilike(f"%{name}%"))
    if inventory_id:
        query = query.where(Asset.inventory_id == inventory_id)
    if serial_number:
        query = query.where(Asset.serial_number == serial_number)
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
        # selectinload(Asset.model).options(
        #     selectinload(AssetModel.asset_type)
        # ),
        selectinload(Asset.parent).options(selectinload(Asset.assignments)),
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

# async def update_asset(db: AsyncSession, asset_id: int, data: AssetUpdate, employee_id: str) -> Optional[Asset]:
#     obj = await get_asset_by_id(db, asset_id)
#     if not obj:
#         return None
#
#     update_data = data.model_dump(exclude_unset=True)
#     for key, value in update_data.items():
#         setattr(obj, key, value)
#     obj.updated_by = employee_id
#
#     await db.commit()
#     return await get_asset_by_id(db, asset_id)

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
    - selected=True: создать привязку (если не существует активная)
    - selected=False: закрыть активную привязку (если существует)
    """
    for user_data in users:
        employee_id = user_data.employee_id
        selected = user_data.selected

        # Проверяем, есть ли активная привязка для этого сотрудника
        result = await db.execute(
            select(AssetAssignment).where(
                AssetAssignment.asset_id == asset_id,
                AssetAssignment.employee_id == employee_id,
                AssetAssignment.end_date.is_(None)
            )
        )
        active_assignment = result.scalar_one_or_none()

        if selected:
            # Привязать пользователя
            if not active_assignment:
                # Создаем новую привязку
                new_assignment = AssetAssignment(
                    asset_id=asset_id,
                    employee_id=employee_id,
                    start_date=date.today(),
                    end_date=None,
                    assigned_by=assigned_by
                )
                db.add(new_assignment)
        else:
            # Отвязать пользователя
            if active_assignment:
                active_assignment.end_date = date.today()

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