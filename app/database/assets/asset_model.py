from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.assets.asset_model import AssetModel
from app.models.assets import AssetClass
from app.schemas.assets.asset_model import AssetModelCreate, AssetModelUpdate


async def get_asset_model_by_id(db: AsyncSession, model_id: int) -> Optional[AssetModel]:
    result = await db.execute(
        select(AssetModel)
        .options(
            selectinload(AssetModel.asset_class).options(
                selectinload(AssetClass.asset_type)
            ),
            selectinload(AssetModel.creator),
            selectinload(AssetModel.updater)
        )
        .where(AssetModel.model_id == model_id)
    )
    return result.scalar_one_or_none()


async def create_asset_model(db: AsyncSession, data: AssetModelCreate, employee_id: str) -> AssetModel | None:
    db_obj = AssetModel(**data.model_dump(), created_by=employee_id, updated_by=employee_id)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    # return db_obj
    return await get_asset_model_by_id(db, db_obj.model_id)


async def get_asset_models_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        model_name: Optional[str] = None,
        class_id: Optional[int] = None
) -> Sequence[AssetModel]:
    query = select(AssetModel).options(
        selectinload(AssetModel.asset_class).options(
            selectinload(AssetClass.asset_type)
        ),
        selectinload(AssetModel.creator),
        selectinload(AssetModel.updater)
    )

    if model_name:
        query = query.where(AssetModel.model_name.ilike(f"%{model_name}%"))
    if class_id is not None:
        query = query.where(AssetModel.class_id == class_id)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_asset_model(db: AsyncSession, model_id: int, data: AssetModelUpdate, employee_id: str) -> Optional[AssetModel]:
    obj = await get_asset_model_by_id(db, model_id)
    if not obj:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(obj, key, value)
    obj.updated_by = employee_id

    await db.commit()
    await db.refresh(obj)
    # return obj
    return await get_asset_model_by_id(db, obj.model_id)


async def delete_asset_model(db: AsyncSession, model_id: int) -> bool:
    obj = await get_asset_model_by_id(db, model_id)
    if not obj:
        return False

    await db.delete(obj)
    await db.commit()
    return True