from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.assets.asset_model import AssetModel
from app.schemas.assets.asset_model import AssetModelCreate, AssetModelUpdate


async def get_asset_model_by_id(db: AsyncSession, model_id: int) -> Optional[AssetModel]:
    result = await db.execute(
        select(AssetModel)
        .options(selectinload(AssetModel.asset_type))
        .where(AssetModel.model_id == model_id)
    )
    return result.scalar_one_or_none()


async def get_asset_models_list(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[AssetModel]:
    query = select(AssetModel).options(selectinload(AssetModel.asset_type)).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def create_asset_model(db: AsyncSession, model_in: AssetModelCreate, employee_id: str) -> AssetModel:
    db_model = AssetModel(**model_in.model_dump(), created_by=employee_id, updated_by=employee_id)
    db.add(db_model)
    await db.commit()
    await db.refresh(db_model)
    return await get_asset_model_by_id(db, db_model.model_id)


async def update_asset_model(db: AsyncSession, model_id: int, model_in: AssetModelUpdate, employee_id: str) -> Optional[AssetModel]:
    model = await get_asset_model_by_id(db, model_id)
    if not model:
        return None

    update_data = model_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(model, key, value)
    model.updated_by = employee_id

    await db.commit()
    return await get_asset_model_by_id(db, model_id)


async def delete_asset_model(db: AsyncSession, model_id: int) -> bool:
    model = await get_asset_model_by_id(db, model_id)
    if not model:
        return False

    await db.delete(model)
    await db.commit()
    return True