from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.assets.asset_type import AssetType
from app.schemas.assets.asset_type import AssetTypeCreate, AssetTypeUpdate


async def create_asset_type(db: AsyncSession, data: AssetTypeCreate, employee_id: str) -> AssetType:
    db_obj = AssetType(**data.model_dump(), created_by=employee_id)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def get_asset_type_by_id(db: AsyncSession, asset_type_id: int) -> Optional[AssetType]:
    result = await db.execute(
        select(AssetType)
        .options(selectinload(AssetType.creator))
        .where(AssetType.asset_type_id == asset_type_id)
    )
    return result.scalar_one_or_none()


async def get_asset_types_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        name: Optional[str] = None,
        en_name: Optional[str] = None
) -> Sequence[AssetType]:
    query = select(AssetType).options(selectinload(AssetType.creator))

    if name:
        query = query.where(AssetType.name.ilike(f"%{name}%"))
    if en_name:
        query = query.where(AssetType.en_name.ilike(f"%{en_name}%"))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_asset_type(db: AsyncSession, asset_type_id: int, data: AssetTypeUpdate) -> Optional[AssetType]:
    obj = await get_asset_type_by_id(db, asset_type_id)
    if not obj:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(obj, key, value)

    await db.commit()
    await db.refresh(obj)
    return obj


async def delete_asset_type(db: AsyncSession, asset_type_id: int) -> bool:
    obj = await get_asset_type_by_id(db, asset_type_id)
    if not obj:
        return False

    await db.delete(obj)
    await db.commit()
    return True