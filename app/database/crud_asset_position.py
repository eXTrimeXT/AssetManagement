from typing import Optional, List, Any, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError

from app.models.AssetPosition import AssetPosition
from app.models.Workshop import Workshop
from app.models.Asset import Asset
from app.schemas.asset_position.AssetPosition import AssetPositionCreate, AssetPositionUpdate


async def create_position(db: AsyncSession, data: AssetPositionCreate) -> AssetPosition:
    """
    Создание новой позиции актива на карте.
    """
    # Проверяем существование актива и цеха
    asset = await db.get(Asset, data.asset_id)
    if not asset:
        raise ValueError(f"Asset with id {data.asset_id} not found.")

    workshop = await db.get(Workshop, data.workshop_id)
    if not workshop:
        raise ValueError(f"Workshop with id {data.workshop_id} not found.")

    try:
        # Если уже есть активная позиция для этого актива, деактивируем её
        await deactivate_asset_position(db, data.asset_id)

        new_position = AssetPosition(**data.model_dump())
        db.add(new_position)
        await db.commit()
        await db.refresh(new_position)
        return new_position
    except IntegrityError:
        await db.rollback()
        raise ValueError("Failed to create position.")


async def get_position(db: AsyncSession, position_id: int) -> type[AssetPosition] | Any:
    """
    Получение позиции по ID.
    """
    return await db.get(AssetPosition, position_id)


async def get_positions_by_workshop(db: AsyncSession, workshop_id: int, skip: int = 0, limit: int = 100) -> Sequence[
    Any]:
    """
    Получение всех активных позиций для конкретного цеха.
    """
    result = await db.execute(
        select(AssetPosition)
        .where(
            AssetPosition.workshop_id == workshop_id,
            AssetPosition.is_active == True
        )
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def update_position(db: AsyncSession, position_id: int, data: AssetPositionUpdate) -> type[
                                                                                                AssetPosition] | None | Any:
    """
    Обновление позиции (перемещение).
    """
    try:
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return await get_position(db, position_id)

        stmt = update(AssetPosition).where(AssetPosition.id == position_id).values(**update_data)
        result = await db.execute(stmt)
        await db.commit()

        if result.rowcount > 0:
            return await get_position(db, position_id)
        return None
    except IntegrityError:
        await db.rollback()
        raise ValueError("Failed to update position.")


async def delete_position(db: AsyncSession, position_id: int) -> bool:
    """
    Удаление позиции.
    """
    stmt = delete(AssetPosition).where(AssetPosition.id == position_id)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0


async def deactivate_asset_position(db: AsyncSession, asset_id: int) -> None:
    """
    Деактивация всех текущих позиций актива (для истории).
    Вызывается перед созданием новой позиции.
    """
    stmt = (
        update(AssetPosition)
        .where(AssetPosition.asset_id == asset_id, AssetPosition.is_active == True)
        .values(is_active=False)
    )
    await db.execute(stmt)
    # Коммит здесь не делаем, чтобы транзакция была атомарной в create_position