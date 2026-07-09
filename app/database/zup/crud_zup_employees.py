from typing import Optional, Sequence, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.zup.employee import Employee
from app.models.zup.department import ZupDepartment
from app.schemas.zup.employee_schemas import EmployeeCreate, EmployeeUpdate
from app.database.zup.crud_zup_departments import get_hierarchy_departments
from app.schemas.zup import DepartmentDivisionGroupResponse


async def get_employee_by_guid(db: AsyncSession, guid: str) -> Optional[Employee]:
    result = await db.execute(select(Employee).where(Employee.guid == guid))
    return result.scalar_one_or_none()


async def get_employee_by_id(db: AsyncSession, employee_id: str) -> Optional[Employee]:
    result = await db.execute(select(Employee).where(Employee.employee_id == employee_id))
    return result.scalar_one_or_none()


async def get_employee_by_login_or_email(
        db: AsyncSession,
        login: str,
        email: Optional[str] = None
) -> Optional[Employee]:
    if email:
        result = await db.execute(select(Employee).where(Employee.email == email))
        employee = result.scalar_one_or_none()
        if employee:
            return employee

    if login and len(login) > 4:
        login_suffix = login[4:]
        result = await db.execute(
            select(Employee).where(func.substring(Employee.employee_id, 5) == login_suffix)
        )
        employee = result.scalar_one_or_none()
        if employee:
            return employee

    result = await db.execute(select(Employee).where(Employee.employee_id == login))
    return result.scalar_one_or_none()


async def create_employee(db: AsyncSession, employee_in: EmployeeCreate) -> Employee:
    db_employee = Employee(**employee_in.model_dump())
    db.add(db_employee)
    await db.commit()
    await db.refresh(db_employee)
    return db_employee


async def update_employee(db: AsyncSession, guid: str, employee_in: EmployeeUpdate) -> Optional[Employee]:
    employee = await get_employee_by_guid(db, guid)
    if not employee:
        return None
    update_data = employee_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(employee, key, value)
    await db.commit()
    await db.refresh(employee)
    return employee


async def get_employees_count(
        db: AsyncSession,
        employee_id: Optional[str] = None,
        last_name: Optional[str] = None,
        first_name: Optional[str] = None,
        middle_name: Optional[str] = None,
        last_name_en: Optional[str] = None,
        first_name_en: Optional[str] = None,
        middle_name_en: Optional[str] = None,
        department_guid: Optional[str] = None,
        position_guid: Optional[str] = None,
        is_active: Optional[bool] = None
) -> int:
    query = select(func.count(Employee.employee_id))
    if employee_id:
        query = query.where(Employee.employee_id == employee_id)
    if last_name:
        query = query.where(Employee.last_name.ilike(f"%{last_name}%"))
    if first_name:
        query = query.where(Employee.first_name.ilike(f"%{first_name}%"))
    if middle_name:
        query = query.where(Employee.middle_name.ilike(f"%{middle_name}%"))
    if last_name_en:
        query = query.where(Employee.last_name_en.ilike(f"%{last_name_en}%"))
    if first_name_en:
        query = query.where(Employee.first_name_en.ilike(f"%{first_name_en}%"))
    if middle_name_en:
        query = query.where(Employee.middle_name_en.ilike(f"%{middle_name_en}%"))
    if department_guid:
        query = query.where(Employee.department_guid == department_guid)
    if position_guid:
        query = query.where(Employee.position_guid == position_guid)
    if is_active is not None:
        if is_active:
            query = query.where(Employee.dismissal_date.is_(None))
        else:
            query = query.where(Employee.dismissal_date.isnot(None))
    result = await db.execute(query)
    return result.scalar() or 0


async def get_employees_list(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 50,
        employee_id: Optional[str] = None,
        last_name: Optional[str] = None,
        first_name: Optional[str] = None,
        middle_name: Optional[str] = None,
        last_name_en: Optional[str] = None,
        first_name_en: Optional[str] = None,
        middle_name_en: Optional[str] = None,
        department_guid: Optional[str] = None,
        position_guid: Optional[str] = None,
        is_active: Optional[bool] = None
) -> Tuple[Sequence[Employee], int]:
    """
    Получить страницу сотрудников с фильтрацией.
    Возвращает кортеж: (список сотрудников, общее количество).

    После загрузки заполняет вычисляемые поля:
    - group (1-й уровень)
    - division (2-й уровень, parent от group)
    - department (3-й уровень, parent от division)
    """
    total = await get_employees_count(
        db, employee_id, last_name, first_name, middle_name,
        last_name_en, first_name_en, middle_name_en,
        department_guid, position_guid, is_active
    )

    skip = (page - 1) * page_size

    # Загружаем сотрудников с position и цепочкой parent (3 уровня)
    query = (
        select(Employee)
        .options(
            selectinload(Employee.position),
            selectinload(Employee.group).options(
                selectinload(ZupDepartment.parent).options(
                    selectinload(ZupDepartment.parent)
                )
            )
        )
    )

    if employee_id:
        query = query.where(Employee.employee_id == employee_id)
    if last_name:
        query = query.where(Employee.last_name.ilike(f"%{last_name}%"))
    if first_name:
        query = query.where(Employee.first_name.ilike(f"%{first_name}%"))
    if middle_name:
        query = query.where(Employee.middle_name.ilike(f"%{middle_name}%"))
    if last_name_en:
        query = query.where(Employee.last_name_en.ilike(f"%{last_name_en}%"))
    if first_name_en:
        query = query.where(Employee.first_name_en.ilike(f"%{first_name_en}%"))
    if middle_name_en:
        query = query.where(Employee.middle_name_en.ilike(f"%{middle_name_en}%"))
    if department_guid:
        query = query.where(Employee.department_guid == department_guid)
    if position_guid:
        query = query.where(Employee.position_guid == position_guid)
    if is_active is not None:
        if is_active:
            query = query.where(Employee.dismissal_date.is_(None))
        else:
            query = query.where(Employee.dismissal_date.isnot(None))

    query = query.order_by(Employee.employee_id)
    query = query.offset(skip).limit(page_size)

    result = await db.execute(query)
    employees = result.scalars().all()

    # # Раскладываем иерархию по плоским полям
    # for emp in employees:
    #     group = emp.group  # 1-й уровень (группа)
    #     division = group.parent if group else None  # 2-й уровень (отдел)
    #     department = division.parent if division else None  # 3-й уровень (департамент)
    #
    #     emp.group = group
    #     emp.workplace = group
    #     emp.division = division
    #     emp.department = department

    for emp in employees:
        ddgr: Optional[DepartmentDivisionGroupResponse] = await get_hierarchy_departments(db, emp.department_guid)
        emp.society = ddgr.society if ddgr.society else None
        emp.department = ddgr.department if ddgr.department else None
        emp.division = ddgr.division if ddgr.division else None
        emp.group = ddgr.group if ddgr.group else None

    return employees, total


async def upsert_employee(db: AsyncSession, employee_data: dict) -> Employee:
    employee = await get_employee_by_guid(db, employee_data["guid"])
    if employee:
        for key, value in employee_data.items():
            if hasattr(employee, key):
                setattr(employee, key, value)
    else:
        employee = Employee(**employee_data)
        db.add(employee)
    await db.commit()
    await db.refresh(employee)
    return employee