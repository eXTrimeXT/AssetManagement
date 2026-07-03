from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.zup.manager import Manager
from app.schemas.zup.manager_schemas import ManagerCreate


async def get_manager_by_id(db: AsyncSession, id: str) -> Optional[Manager]:
    result = await db.execute(select(Manager).where(Manager.id == id))
    return result.scalar_one_or_none()


async def create_manager(db: AsyncSession, manager_in: ManagerCreate) -> Manager:
    db_manager = Manager(**manager_in.model_dump())
    db.add(db_manager)
    await db.commit()
    await db.refresh(db_manager)
    return db_manager


async def get_managers_list(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[Manager]:
    query = select(Manager).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def upsert_manager(db: AsyncSession, manager_data: dict) -> Manager:
    manager = await get_manager_by_id(db, manager_data["id"])

    if manager:
        for key, value in manager_data.items():
            if hasattr(manager, key):
                setattr(manager, key, value)
    else:
        manager = Manager(**manager_data)
        db.add(manager)

    await db.commit()
    await db.refresh(manager)
    return manager