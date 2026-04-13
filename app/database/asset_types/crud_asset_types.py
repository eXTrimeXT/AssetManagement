from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.AssetType import AssetType
from app.schemas.AssetTypes import AssetTypeCreate, AssetTypeUpdate
from typing import Sequence


async def create_asset_type(db: AsyncSession, data: AssetTypeCreate) -> AssetType:
    """Создание типа актива"""
    db_obj = AssetType(**data.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_asset_type_by_type_id(db: AsyncSession, type_id: int) -> AssetType | None:
    """Получение по бизнес-коду (type_id)"""
    result = await db.execute(select(AssetType).where(AssetType.type_id == type_id))
    return result.scalar_one_or_none()

async def get_asset_type_by_id(db: AsyncSession, asset_type_id: int) -> type[AssetType] | None:
    """Получение по первичному ключу (asset_type_id)"""
    return await db.get(AssetType, asset_type_id)

async def list_asset_types(db: AsyncSession) -> Sequence[AssetType]:
    """Полный список типов"""
    result = await db.execute(select(AssetType))
    return result.scalars().all()

async def update_asset_type(db: AsyncSession, db_obj: AssetType, data: AssetTypeUpdate) -> AssetType:
    """Частичное обновление (PATCH)"""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_obj, key, value)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def delete_asset_type(db: AsyncSession, db_obj: AssetType) -> None:
    """Физическое удаление"""
    await db.delete(db_obj)
    await db.commit()