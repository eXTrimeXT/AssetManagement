from typing import Optional, List
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.map_assets.Workshop import Workshop
from app.schemas.map_assets.WorkshopCreate import WorkshopCreate
from app.schemas.map_assets.WorkshopUpdate import WorkshopUpdate

async def create_workshop(db: AsyncSession, workshop_data: WorkshopCreate) -> Workshop:
    """Создать новый цех"""
    workshop = Workshop(**workshop_data.model_dump())
    db.add(workshop)
    await db.commit()
    await db.refresh(workshop)
    return workshop

async def get_workshop(db: AsyncSession, workshop_id: int) -> Optional[Workshop]:
    """Получить цех по ID"""
    result = await db.execute(
        select(Workshop).where(Workshop.workshop_id == workshop_id)
    )
    return result.scalar_one_or_none()

async def get_workshop_by_code(db: AsyncSession, code: str) -> Optional[Workshop]:
    """Получить цех по коду"""
    result = await db.execute(
        select(Workshop).where(Workshop.code == code)
    )
    return result.scalar_one_or_none()

async def get_all_workshop(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Workshop]:
    """Получить все цеха"""
    result = await db.execute(
        select(Workshop)
        .where(Workshop.is_active == True)
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())

async def update_workshop(
        db: AsyncSession, workshop_id: int, workshop_data: WorkshopUpdate
) -> Optional[Workshop]:
    """Обновить цех"""
    update_data = workshop_data.model_dump(exclude_unset=True)
    if not update_data:
        return await get_workshop(db, workshop_id)

    await db.execute(
        update(Workshop)
        .where(Workshop.workshop_id == workshop_id)
        .values(**update_data)
    )
    await db.commit()
    return await get_workshop(db, workshop_id)

async def delete_workshop(db: AsyncSession, workshop_id: int) -> bool:
    """Удалить цех (мягкое удаление)"""
    await db.execute(
        update(Workshop)
        .where(Workshop.workshop_id == workshop_id)
        .values(is_active=False)
    )
    await db.commit()
    return True

async def hard_delete_workshop(db: AsyncSession, workshop_id: int) -> bool:
    """Полностью удалить цех из базы"""
    await db.execute(
        delete(Workshop).where(Workshop.workshop_id == workshop_id)
    )
    await db.commit()
    return True