from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.zup.position import Position
from app.schemas.zup.position_schemas import PositionCreate, PositionUpdate


async def get_position_by_guid(db: AsyncSession, guid: str) -> Optional[Position]:
    result = await db.execute(select(Position).where(Position.guid == guid))
    return result.scalar_one_or_none()


async def create_position(db: AsyncSession, position_in: PositionCreate) -> Position:
    db_position = Position(**position_in.model_dump())
    db.add(db_position)
    await db.commit()
    await db.refresh(db_position)
    return db_position


async def update_position(db: AsyncSession, guid: str, position_in: PositionUpdate) -> Optional[Position]:
    position = await get_position_by_guid(db, guid)
    if not position:
        return None

    update_data = position_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(position, key, value)

    await db.commit()
    await db.refresh(position)
    return position


async def get_positions_list(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[Position]:
    query = select(Position).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def upsert_position(db: AsyncSession, position_data: dict) -> Position:
    position = await get_position_by_guid(db, position_data["guid"])

    if position:
        for key, value in position_data.items():
            if hasattr(position, key):
                setattr(position, key, value)
    else:
        position = Position(**position_data)
        db.add(position)

    await db.commit()
    await db.refresh(position)
    return position