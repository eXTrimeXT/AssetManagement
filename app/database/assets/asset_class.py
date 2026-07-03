from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.assets.asset_class import AssetClass
from app.schemas.assets.asset_class import AssetClassCreate, AssetClassUpdate


async def get_asset_class_by_id(db: AsyncSession, class_id: int) -> Optional[AssetClass]:
    result = await db.execute(
        select(AssetClass)
        .options(
            selectinload(AssetClass.asset_type),
            selectinload(AssetClass.creator),
            selectinload(AssetClass.updater)
        )
        .where(AssetClass.class_id == class_id)
    )
    return result.scalar_one_or_none()


async def create_asset_class(db: AsyncSession, data: AssetClassCreate, employee_id: str) -> AssetClass | None:
    db_obj = AssetClass(**data.model_dump(), created_by=employee_id, updated_by=employee_id)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    # return db_obj
    # Перезагружаем объект с загруженными связями для корректной сериализации
    return await get_asset_class_by_id(db, db_obj.class_id)


async def get_asset_classes_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        class_name: Optional[str] = None,
        asset_type_id: Optional[int] = None
) -> Sequence[AssetClass]:
    query = select(AssetClass).options(
        selectinload(AssetClass.asset_type),
        selectinload(AssetClass.creator),
        selectinload(AssetClass.updater)
    )

    if class_name:
        query = query.where(AssetClass.class_name.ilike(f"%{class_name}%"))
    if asset_type_id is not None:
        query = query.where(AssetClass.asset_type_id == asset_type_id)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_asset_class(db: AsyncSession, class_id: int, data: AssetClassUpdate, employee_id: str) -> Optional[AssetClass]:
    obj = await get_asset_class_by_id(db, class_id)
    if not obj:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(obj, key, value)
    obj.updated_by = employee_id

    await db.commit()
    await db.refresh(obj)
    # return obj
    # Перезагружаем с загруженными связями
    return await get_asset_class_by_id(db, class_id)


async def delete_asset_class(db: AsyncSession, class_id: int) -> bool:
    obj = await get_asset_class_by_id(db, class_id)
    if not obj:
        return False

    await db.delete(obj)
    await db.commit()
    return True