from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.assets.AssetStatus import AssetStatus
from app.schemas.assets.AssetStatusSchemas import AssetStatusCreate
from app.schemas.assets.AssetStatusSchemas import AssetStatusUpdate

async def create_asset_status(db: AsyncSession, status_data: AssetStatusCreate):
    db_status = AssetStatus(status=status_data.status)
    db.add(db_status)
    await db.commit()
    await db.refresh(db_status)
    return db_status

async def get_asset_statuses(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(select(AssetStatus).offset(skip).limit(limit))
    return result.scalars().all()

async def get_asset_status(db: AsyncSession, status_id: int):
    return await db.get(AssetStatus, status_id)

async def update_asset_status(db: AsyncSession, status_id: int, status_data: AssetStatusUpdate):
    db_status = await db.get(AssetStatus, status_id)
    if db_status:
        db_status.status = status_data.status
        await db.commit()
        await db.refresh(db_status)
    return db_status

async def delete_asset_status(db: AsyncSession, status_id: int):
    db_status = await db.get(AssetStatus, status_id)
    if db_status:
        await db.delete(db_status)
        await db.commit()
    return db_status