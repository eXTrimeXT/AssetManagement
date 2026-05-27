from typing import Optional, Sequence, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.Department import Department
from app.schemas.departments.DepartmentCreate import DepartmentCreate
from app.schemas.departments.DepartmentUpdate import DepartmentUpdate


async def get_department_by_id(db: AsyncSession, department_id: int) -> Optional[Department]:
    result = await db.execute(
        select(Department).where(Department.id == department_id)
    )
    return result.scalar_one_or_none()


async def create_department(db: AsyncSession, department_in: DepartmentCreate) -> Department:
    db_department = Department(**department_in.model_dump())
    db.add(db_department)
    try:
        await db.commit()
        await db.refresh(db_department)
        return db_department
    except IntegrityError:
        await db.rollback()
        raise  # Пробрасываем ошибку дальше, обработаем в router


async def get_departments_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        name: Optional[str] = None,
        abbreviation: Optional[str] = None
) -> Sequence[Any]:
    query = select(Department)

    if name:
        query = query.where(Department.name.ilike(f"%{name}%"))
    if abbreviation:
        query = query.where(Department.abbreviation.ilike(f"%{abbreviation}%"))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_department(
        db: AsyncSession,
        department_id: int,
        department_data: DepartmentUpdate
) -> Optional[Department]:
    department = await get_department_by_id(db, department_id)
    if not department:
        return None

    update_data = department_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(department, key, value)

    try:
        await db.commit()
        await db.refresh(department)
        return department
    except IntegrityError:
        await db.rollback()
        raise


async def delete_department(db: AsyncSession, department_id: int) -> bool:
    department = await get_department_by_id(db, department_id)
    if not department:
        return False

    await db.delete(department)
    await db.commit()
    return True