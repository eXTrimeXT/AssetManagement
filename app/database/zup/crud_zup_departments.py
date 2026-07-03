from typing import Optional, Sequence, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.zup.department import ZupDepartment
from app.schemas.zup.department_schemas import DepartmentCreate, DepartmentUpdate


async def get_department_by_guid(db: AsyncSession, guid: str) -> Optional[ZupDepartment]:
    result = await db.execute(select(ZupDepartment).where(ZupDepartment.guid == guid))
    return result.scalar_one_or_none()


async def create_department(db: AsyncSession, department_in: DepartmentCreate) -> ZupDepartment:
    db_department = ZupDepartment(**department_in.model_dump())
    db.add(db_department)
    await db.commit()
    await db.refresh(db_department)
    return db_department


async def update_department(db: AsyncSession, guid: str, department_in: DepartmentUpdate) -> Optional[ZupDepartment]:
    department = await get_department_by_guid(db, guid)
    if not department:
        return None

    update_data = department_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(department, key, value)

    await db.commit()
    await db.refresh(department)
    return department


async def get_departments_list(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[ZupDepartment]:
    query = select(ZupDepartment).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def upsert_department(db: AsyncSession, department_data: dict) -> ZupDepartment:
    department = await get_department_by_guid(db, department_data["guid"])

    if department:
        for key, value in department_data.items():
            if hasattr(department, key):
                setattr(department, key, value)
    else:
        department = ZupDepartment(**department_data)
        db.add(department)

    await db.commit()
    await db.refresh(department)
    return department