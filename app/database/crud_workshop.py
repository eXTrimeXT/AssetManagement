from typing import Optional, List, Any, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError

from app.models.Workshop import Workshop
from app.schemas.workshop.Workshop import WorkshopCreate, WorkshopUpdate


async def create_workshop(db: AsyncSession, data: WorkshopCreate) -> Workshop:
    """
    Создание нового цеха.
    """
    try:
        # Исключаем map_size из создания
        workshop_data = data.model_dump(exclude={'map_size'})
        new_workshop = Workshop(**workshop_data)

        # Устанавливаем hardcoded значения
        new_workshop.map_size = 4000

        db.add(new_workshop)
        await db.commit()
        await db.refresh(new_workshop)
        return new_workshop
    except IntegrityError:
        await db.rollback()
        raise ValueError(f"Workshop with code '{data.code}' already exists.")


async def get_workshop(db: AsyncSession, workshop_id: int) -> Optional[Workshop]:
    """
    Получение цеха по ID.
    """
    result = await db.execute(select(Workshop).where(Workshop.workshop_id == workshop_id))
    return result.scalar_one_or_none()


async def get_workshops(db: AsyncSession, skip: int = 0, limit: int = 100) -> Sequence[Any]:
    """
    Получение списка цехов с пагинацией.
    """
    result = await db.execute(
        select(Workshop)
        .offset(skip)
        .limit(limit)
        .order_by(Workshop.workshop_id)
    )
    return result.scalars().all()


async def update_workshop(db: AsyncSession, workshop_id: int, data: WorkshopUpdate) -> Optional[Workshop]:
    """
    Обновление данных цеха.
    """
    try:
        update_data = data.model_dump(exclude_unset=True, exclude={'map_size'})
        if not update_data:
            return await get_workshop(db, workshop_id)

        stmt = update(Workshop).where(Workshop.workshop_id == workshop_id).values(**update_data)
        result = await db.execute(stmt)
        await db.commit()

        if result.rowcount > 0:
            return await get_workshop(db, workshop_id)
        return None
    except IntegrityError:
        await db.rollback()
        raise ValueError("Failed to update workshop. Possible unique constraint violation.")


async def delete_workshop(db: AsyncSession, workshop_id: int) -> bool:
    """
    Удаление цеха.
    """
    stmt = delete(Workshop).where(Workshop.workshop_id == workshop_id)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0