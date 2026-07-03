from typing import Optional, Sequence, List, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.assets.asset import Asset
from app.models.assets.asset_model import AssetModel
from app.models.assets.asset_class import AssetClass
from app.schemas.assets.asset import AssetCreate, AssetUpdate


async def create_asset(db: AsyncSession, data: AssetCreate, employee_id: str) -> Asset | None:
    """Создать новый актив"""
    db_obj = Asset(**data.model_dump(), created_by=employee_id, updated_by=employee_id)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    # Перезагружаем с связями
    return await get_asset_by_id(db, db_obj.asset_id)


async def get_asset_by_id(db: AsyncSession, asset_id: int) -> Optional[Asset]:
    """Получить актив по ID с загруженными связями"""
    result = await db.execute(
        select(Asset)
        .options(
            # Правильный синтаксис для вложенных связей
            selectinload(Asset.model).options(
                selectinload(AssetModel.asset_class).options(
                    selectinload(AssetClass.asset_type)
                )
            ),
            selectinload(Asset.parent),
            selectinload(Asset.preparer),
            selectinload(Asset.checker),
            selectinload(Asset.creator),
            selectinload(Asset.updater)
        )
        .where(Asset.asset_id == asset_id)
    )
    return result.scalar_one_or_none()


async def get_assets_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        name: Optional[str] = None,
        inventory_id: Optional[str] = None,
        serial_number: Optional[str] = None,
        asset_status: Optional[str] = None,
        model_id: Optional[int] = None,
        parent_id: Optional[int] = None
) -> Sequence[Asset]:
    """Получение списка активов с фильтрацией"""
    query = select(Asset).options(
        selectinload(Asset.model).options(
            selectinload(AssetModel.asset_class).options(
                selectinload(AssetClass.asset_type)
            )
        ),
        selectinload(Asset.parent)
    )

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
    if parent_id is not None:
        query = query.where(Asset.parent_id == parent_id)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_asset(db: AsyncSession, asset_id: int, data: AssetUpdate, employee_id: str) -> Optional[Asset]:
    """Обновить актив"""
    obj = await get_asset_by_id(db, asset_id)
    if not obj:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(obj, key, value)
    obj.updated_by = employee_id

    await db.commit()
    return await get_asset_by_id(db, asset_id)


async def delete_asset(db: AsyncSession, asset_id: int) -> bool:
    """Hard delete актива и всех его детей"""
    obj = await get_asset_by_id(db, asset_id)
    if not obj:
        return False

    await db.delete(obj)
    await db.commit()
    return True


async def get_asset_children(db: AsyncSession, asset_id: int) -> Sequence[Any]:
    """Получение всех детей актива через parent_id"""
    result = await db.execute(
        select(Asset)
        .options(
            selectinload(Asset.model).options(
                selectinload(AssetModel.asset_class).options(
                    selectinload(AssetClass.asset_type)
                )
            ),
            selectinload(Asset.parent)
        )
        .where(Asset.parent_id == asset_id)
    )
    return result.scalars().all()

async def get_asset_children_with_permissions(
        db: AsyncSession,
        asset_id: int,
        employee_id: str
) -> Sequence[Any]:
    """Получение детей актива с проверкой прав (вариант 3)"""
    # Здесь должна быть логика проверки прав на каждого ребенка
    # Для примера возвращаем всех детей
    return await get_asset_children(db, asset_id)