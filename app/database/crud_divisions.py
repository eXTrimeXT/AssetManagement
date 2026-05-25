from typing import Optional, Sequence, Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.Division import Division
from app.schemas.divisions.DivisionCreate import DivisionCreate
from app.schemas.divisions.DivisionUpdate import DivisionUpdate


async def get_division_by_id(db: AsyncSession, division_id: int) -> Optional[Division]:
    result = await db.execute(
        select(Division).where(Division.id == division_id)
    )
    return result.scalar_one_or_none()


async def create_division(db: AsyncSession, division_in: DivisionCreate) -> Division:
    db_division = Division(**division_in.model_dump())
    db.add(db_division)
    try:
        await db.commit()
        await db.refresh(db_division)
        return db_division
    except IntegrityError:
        await db.rollback()
        raise


async def get_divisions_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        name: Optional[str] = None,
        abbreviation: Optional[str] = None,
        department_id: Optional[int] = None
) -> Sequence[Any]:
    query = select(Division)

    if name:
        query = query.where(Division.name.ilike(f"%{name}%"))
    if abbreviation:
        query = query.where(Division.abbreviation.ilike(f"%{abbreviation}%"))
    if department_id:
        query = query.where(Division.department_id == department_id)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_division(
        db: AsyncSession,
        division_id: int,
        division_data: DivisionUpdate
) -> Optional[Division]:
    division = await get_division_by_id(db, division_id)
    if not division:
        return None

    update_data = division_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(division, key, value)

    try:
        await db.commit()
        await db.refresh(division)
        return division
    except IntegrityError:
        await db.rollback()
        raise


async def delete_division(db: AsyncSession, division_id: int) -> bool:
    division = await get_division_by_id(db, division_id)
    if not division:
        return False

    await db.delete(division)
    await db.commit()
    return True