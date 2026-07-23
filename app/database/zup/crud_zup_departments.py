from typing import Optional, Sequence, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.zup.department import ZupDepartment
from app.schemas.zup.DepartmentSchemas import DepartmentCreate, DepartmentUpdate, WorkplaceResponse, DepartmentDivisionGroupResponse


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


async def get_hierarchy_departments(
        db: AsyncSession,
        guid: str
) -> Optional[DepartmentDivisionGroupResponse]:
    """
    Получить плоскую иерархию подразделений от группы до общества.

    Логика:
    - guid — это группа (самый нижний уровень, chain[0])
    - Идём вверх по parent_guid, собирая цепочку
    - Общество определяется по признаку parent_guid == NULL_GUID
    - Остальные уровни раскладываются по позиции:
        chain[0] = group
        chain[1] = division (отдел)
        chain[2] = department (департамент)
    """

    # Константа — "пустой" GUID, обозначающий корень иерархии (общество)
    NULL_GUID = "00000000-0000-0000-0000-000000000000"

    if not guid:
        return None

    # Собираем цепочку от группы вверх
    chain: List[ZupDepartment] = []
    current_guid = guid
    visited = set()  # Защита от циклов

    while current_guid and current_guid != NULL_GUID and current_guid not in visited:
        visited.add(current_guid)
        dept = await get_department_by_guid(db, current_guid)
        if not dept:
            break
        chain.append(dept)
        current_guid = dept.parent_guid

    if not chain:
        return None

    def to_workplace(department: Optional[ZupDepartment]) -> Optional[WorkplaceResponse]:
        if not department:
            return None
        return WorkplaceResponse.model_validate(department)

    return DepartmentDivisionGroupResponse(
        society=to_workplace(chain[-1]) if len(chain) >= 1 else None,
        department=to_workplace(chain[-2]) if len(chain) >= 2 else None,
        division=to_workplace(chain[-3]) if len(chain) >= 3 else None,
        group=to_workplace(chain[-4]) if len(chain) >= 4 else None,
    )

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