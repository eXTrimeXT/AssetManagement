from typing import Optional, List
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assets.Asset import Asset
from app.models.map_assets.AssetPosition import AssetPosition
from app.models.map_assets.Workshop import Workshop
from app.schemas.map_assets.AssetPositionCreate import AssetPositionCreate
from app.schemas.map_assets.AssetPositionUpdate import AssetPositionUpdate


async def create_asset_position(db: AsyncSession, position_data: AssetPositionCreate) -> AssetPosition:
    """
    Создание новой позиции актива на карте.
    Координаты x, y относительны workshop (0,0 = левый верхний угол workshop).
    При сохранении автоматически прибавляется offset цеха.
    """
    # Проверяем существование цеха
    workshop = await db.get(Workshop, position_data.workshop_id)
    if not workshop:
        raise ValueError(f"Workshop with id {position_data.workshop_id} not found.")

    # Проверяем существование актива
    asset = await db.get(Asset, position_data.asset_id)
    if not asset:
        raise ValueError(f"Asset with id {position_data.asset_id} not found.")

    # === ВАЛИДАЦИЯ: проверяем, что координаты в пределах workshop ===
    if workshop.workshop_width and (position_data.x < 0 or position_data.x > workshop.workshop_width):
        raise ValueError(
            f"Coordinate x={position_data.x} is out of bounds. Workshop width={workshop.workshop_width}"
        )

    if workshop.workshop_height and (position_data.y < 0 or position_data.y > workshop.workshop_height):
        raise ValueError(
            f"Coordinate y={position_data.y} is out of bounds. Workshop height={workshop.workshop_height}"
        )

    try:
        # Если уже есть активная позиция для этого актива, деактивируем её (для истории)
        await deactivate_asset_position(db, position_data.asset_id)

        # Прибавляем offset цеха к координатам для получения абсолютных координат
        absolute_x = position_data.x + (workshop.offset_x or 0)
        absolute_y = position_data.y + (workshop.offset_y or 0)

        new_position = AssetPosition(
            asset_id=position_data.asset_id,
            workshop_id=position_data.workshop_id,
            x=absolute_x,
            y=absolute_y,
            rotation=position_data.rotation,
            scale=position_data.scale,
            is_active=position_data.is_active,
            place=position_data.place,
            level=position_data.level,
        )
        db.add(new_position)
        await db.commit()
        await db.refresh(new_position)
        return new_position
    except Exception:
        await db.rollback()
        raise ValueError("Failed to create position.")

async def get_all_asset_positions(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
) -> List[AssetPosition]:
    """
    Получение всех активных позиций всех активов.
    """
    result = await db.execute(
        select(AssetPosition)
        .where(AssetPosition.is_active == True)
        .offset(skip)
        .limit(limit)
        .order_by(AssetPosition.workshop_id, AssetPosition.asset_id)
    )
    return list(result.scalars().all())

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
    """
    Обновление позиции (перемещение).
    Координаты x, y относительны workshop. При сохранении прибавляется offset.
    """
    # Получаем текущую позицию
    position = await get_asset_position(db, position_id)
    if not position:
        return None

    update_data = position_data.model_dump(exclude_unset=True)
    if not update_data:
        return position

    # === ВАЛИДАЦИЯ: если меняются координаты, проверяем границы workshop ===
    if 'x' in update_data or 'y' in update_data:
        workshop = await db.get(Workshop, position.workshop_id)
        if workshop:
            # Вычисляем новые относительные координаты (вычитаем offset)
            new_relative_x = update_data.get('x', position.x - (workshop.offset_x or 0))
            new_relative_y = update_data.get('y', position.y - (workshop.offset_y or 0))

            if workshop.workshop_width and (new_relative_x < 0 or new_relative_x > workshop.workshop_width):
                raise ValueError(
                    f"Coordinate x={new_relative_x} is out of bounds. Workshop width={workshop.workshop_width}"
                )

            if workshop.workshop_height and (new_relative_y < 0 or new_relative_y > workshop.workshop_height):
                raise ValueError(
                    f"Coordinate y={new_relative_y} is out of bounds. Workshop height={workshop.workshop_height}"
                )

            # Прибавляем offset для сохранения абсолютных координат
            if 'x' in update_data:
                update_data['x'] = new_relative_x + (workshop.offset_x or 0)
            if 'y' in update_data:
                update_data['y'] = new_relative_y + (workshop.offset_y or 0)

    try:
        stmt = update(AssetPosition).where(AssetPosition.id == position_id).values(**update_data)
        await db.execute(stmt)
        await db.commit()
        return await get_asset_position(db, position_id)
    except Exception:
        await db.rollback()
        raise ValueError("Failed to update position.")

async def move_asset_position(
        db: AsyncSession, position_id: int, x: int, y: int, rotation: Optional[int] = None
) -> Optional[AssetPosition]:
    """
    Переместить актив на карте.
    Координаты x, y относительны workshop. При сохранении прибавляется offset.
    """
    # Получаем текущую позицию
    position = await get_asset_position(db, position_id)
    if not position:
        return None

    # Получаем workshop для валидации и прибавления offset
    workshop = await db.get(Workshop, position.workshop_id)
    if not workshop:
        raise ValueError(f"Workshop not found for position {position_id}")

    # === ВАЛИДАЦИЯ: проверяем границы workshop ===
    if workshop.workshop_width and (x < 0 or x > workshop.workshop_width):
        raise ValueError(
            f"Coordinate x={x} is out of bounds. Workshop width={workshop.workshop_width}"
        )

    if workshop.workshop_height and (y < 0 or y > workshop.workshop_height):
        raise ValueError(
            f"Coordinate y={y} is out of bounds. Workshop height={workshop.workshop_height}"
        )

    # Прибавляем offset для получения абсолютных координат
    absolute_x = x + (workshop.offset_x or 0)
    absolute_y = y + (workshop.offset_y or 0)

    update_data = {"x": absolute_x, "y": absolute_y}
    if rotation is not None:
        update_data["rotation"] = rotation

    try:
        stmt = update(AssetPosition).where(AssetPosition.id == position_id).values(**update_data)
        await db.execute(stmt)
        await db.commit()
        return await get_asset_position(db, position_id)
    except Exception:
        await db.rollback()
        raise ValueError("Failed to move position.")

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