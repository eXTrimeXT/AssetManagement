from typing import Optional, List
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.map_assets.asset_position import AssetPosition
from app.schemas.map_assets.AssetPositionCreate import AssetPositionCreate
from app.schemas.map_assets.AssetPositionUpdate import AssetPositionUpdate

async def create_asset_position(db: AsyncSession, position_data: AssetPositionCreate) -> AssetPosition:
    """Создать новую позицию актива на карте"""
    position = AssetPosition(**position_data.model_dump())
    db.add(position)
    await db.commit()
    await db.refresh(position)
    return position

async def get_asset_position(db: AsyncSession, position_id: int) -> Optional[AssetPosition]:
    """Получить позицию по ID"""
    result = await db.execute(
        select(AssetPosition).where(AssetPosition.id == position_id)
    )
    return result.scalar_one_or_none()

async def get_by_asset_and_workshop(
        db: AsyncSession, asset_id: int, workshop_id: int
) -> Optional[AssetPosition]:
    """Получить активную позицию актива в конкретном цехе"""
    result = await db.execute(
        select(AssetPosition)
        .where(
            AssetPosition.asset_id == asset_id,
            AssetPosition.workshop_id == workshop_id,
            AssetPosition.is_active == True
        )
    )
    return result.scalar_one_or_none()

async def get_all_asset_position_by_workshop(
        db: AsyncSession, workshop_id: int, skip: int = 0, limit: int = 100
) -> List[AssetPosition]:
    """Получить все активные позиции в цехе"""
    result = await db.execute(
        select(AssetPosition)
        .where(
            AssetPosition.workshop_id == workshop_id,
            AssetPosition.is_active == True
        )
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())

async def get_all_asset_position_by_asset(
        db: AsyncSession, asset_id: int
) -> List[AssetPosition]:
    """Получить все позиции актива (включая неактивные для истории)"""
    result = await db.execute(
        select(AssetPosition)
        .where(AssetPosition.asset_id == asset_id)
        .order_by(AssetPosition.created_at.desc())
    )
    return list(result.scalars().all())

async def update_asset_position(
        db: AsyncSession, position_id: int, position_data: AssetPositionUpdate
) -> Optional[AssetPosition]:
    """Обновить позицию"""
    update_data = position_data.model_dump(exclude_unset=True)
    if not update_data:
        return await get_asset_position(db, position_id)

    await db.execute(
        update(AssetPosition)
        .where(AssetPosition.id == position_id)
        .values(**update_data)
    )
    await db.commit()
    return await get_asset_position(db, position_id)

async def move_asset_position(
        db: AsyncSession, position_id: int, x: int, y: int, rotation: Optional[int] = None
) -> Optional[AssetPosition]:
    """Переместить актив на карте"""
    update_data = {"x": x, "y": y}
    if rotation is not None:
        update_data["rotation"] = rotation

    await db.execute(
        update(AssetPosition)
        .where(AssetPosition.id == position_id)
        .values(**update_data)
    )
    await db.commit()
    return await get_asset_position(db, position_id)

async def delete_asset_position(db: AsyncSession, position_id: int) -> bool:
    """Удалить позицию (мягкое удаление)"""
    await db.execute(
        update(AssetPosition)
        .where(AssetPosition.id == position_id)
        .values(is_active=False)
    )
    await db.commit()
    return True

async def hard_delete_asset_position(db: AsyncSession, position_id: int) -> bool:
    """Полностью удалить позицию из базы"""
    await db.execute(
        delete(AssetPosition).where(AssetPosition.id == position_id)
    )
    await db.commit()
    return True

async def delete_all_asset_position_by_workshop(db: AsyncSession, workshop_id: int) -> int:
    """Удалить все позиции в цехе"""
    result = await db.execute(
        delete(AssetPosition).where(AssetPosition.workshop_id == workshop_id)
    )
    await db.commit()
    return result.rowcount