from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from app.models.AssetType import AssetType
from app.schemas.asset_types.AssetTypesSchemas import AssetTypeCreate, AssetTypeUpdate
from typing import Sequence, Optional


async def create_asset_type(db: AsyncSession, data: AssetTypeCreate) -> AssetType:
    """Создание типа актива"""
    db_obj = AssetType(**data.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_asset_type_by_id(db: AsyncSession, asset_type_id: int) -> type[AssetType] | None:
    """Получение по первичному ключу (asset_type_id)"""
    return await db.get(AssetType, asset_type_id)

async def get_asset_type_by_name_or_en_name(db: AsyncSession, search_name: Optional[str] = None) -> AssetType | None:
    """Получение типа актива по name и/или en_name (точное совпадение)"""
    if not search_name:
        return None

    search_name_lower = search_name.lower()

    query = select(AssetType).where(
        or_(
            func.lower(AssetType.name) == search_name_lower,
            func.lower(AssetType.en_name) == search_name_lower
        )
    )

    result = await db.execute(query)
    return result.scalar_one_or_none()

async def list_asset_types(db: AsyncSession) -> Sequence[AssetType]:
    """Полный список типов с пагинацией"""
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