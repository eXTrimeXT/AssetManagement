import logging
from typing import Optional, Sequence, Tuple, List, Dict, Any

from sqlalchemy import select, func, or_, inspect
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, aliased
from app.models.zup.employee import Employee
from app.models.zup.department import ZupDepartment
from app.models.zup.position import Position
from app.schemas.zup.EmployeeSchemas import EmployeeCreate, EmployeeUpdate

logger = logging.getLogger(__name__)

async def get_employee_by_guid(db: AsyncSession, guid: str) -> Optional[Employee]:
    result = await db.execute(select(Employee).where(Employee.guid == guid))
    return result.scalar_one_or_none()

async def get_employee_by_id(db: AsyncSession, employee_id: str) -> Optional[Employee]:
    result = await db.execute(
        select(Employee)
        .options(
            selectinload(Employee.position),  # Загружаем должность
            selectinload(Employee.group),  # Загружаем департамент
        )
        .where(Employee.employee_id == employee_id)
    )
    return result.scalar_one_or_none()

async def get_employee_by_active_directory_login(
        db: AsyncSession,
        login: str
) -> Employee | None:
    """
    Ищет сотрудника по active_directory_login (логину из токена).
    Это быстрый путь поиска, если сотрудник уже связан с AD логином.
    """
    result = await db.execute(
        select(Employee).where(Employee.active_directory_login == login)
    )
    return result.scalar_one_or_none()

async def get_employee_by_email(
        db: AsyncSession,
        email: str
) -> Employee | None:
    """
    Ищет сотрудника по email.
    """
    result = await db.execute(
        select(Employee).where(Employee.email == email)
    )
    return result.scalar_one_or_none()

async def get_employee_by_login_or_email(
        db: AsyncSession,
        login: str,
        email: str
) -> Employee | None:
    """
    Ищет сотрудника:
    1. Сначала по active_directory_login (быстрый путь)
    2. Если не найден - по email
    """
    # Сначала пытаемся найти по active_directory_login
    employee = await get_employee_by_active_directory_login(db, login)
    if employee:
        return employee

    # Если не нашли - ищем по email
    employee = await get_employee_by_email(db, email)
    return employee

async def update_employee_active_directory_login(
        db: AsyncSession,
        employee: Employee,
        login: str
) -> None:
    """
    Обновляет active_directory_login сотрудника.
    Вызывается при первом входе, когда сотрудник найден по email.
    """
    if employee.active_directory_login != login:
        employee.active_directory_login = login
        await db.commit()

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

async def update_employee_comment(
        db: AsyncSession,
        employee_id: str,
        comment: Optional[str]
) -> Optional[Employee]:
    """
    Обновляет только поле comment сотрудника.
    """
    employee = await get_employee_by_id(db, employee_id)
    if not employee:
        return None

    employee.comment = comment
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
        is_active: Optional[bool] = None,
        search_department: Optional[str] = None,
        search_position: Optional[str] = None
) -> int:
    query = select(func.count(Employee.employee_id))
    if employee_id:
        # query = query.where(Employee.employee_id == employee_id)
        query = query.where(Employee.employee_id.ilike(f"%{employee_id}%"))
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
    if search_position:
        query = _apply_position_search(query, search_position)
    if is_active is not None:
        if is_active:
            query = query.where(Employee.dismissal_date.is_(None))
        else:
            query = query.where(Employee.dismissal_date.isnot(None))
    if search_department:
        query = _apply_department_search(query, search_department)

    result = await db.execute(query)
    return result.scalar() or 0

def _apply_department_search(query, search_department: str):
    """
    Вспомогательная функция: делает JOIN на 4 уровня иерархии подразделений
    и применяет поиск по name, name_en и short_name.
    """
    d1 = aliased(ZupDepartment, name="d1") # Группа
    d2 = aliased(ZupDepartment, name="d2") # Отдел
    d3 = aliased(ZupDepartment, name="d3") # Департамент
    d4 = aliased(ZupDepartment, name="d4") # Общество

    # Последовательно джойним родителя
    query = query.join(d1, Employee.department_guid == d1.guid) \
        .outerjoin(d2, d1.parent_guid == d2.guid) \
        .outerjoin(d3, d2.parent_guid == d3.guid) \
        .outerjoin(d4, d3.parent_guid == d4.guid)

    search_term = f"%{search_department}%"

    # Ищем совпадение хотя бы на одном из уровней
    query = query.where(
        or_(
            d1.name.ilike(search_term), d1.name_en.ilike(search_term), d1.short_name.ilike(search_term),
            d2.name.ilike(search_term), d2.name_en.ilike(search_term), d2.short_name.ilike(search_term),
            d3.name.ilike(search_term), d3.name_en.ilike(search_term), d3.short_name.ilike(search_term),
            d4.name.ilike(search_term), d4.name_en.ilike(search_term), d4.short_name.ilike(search_term),
        )
    )
    return query


def _apply_position_search(query, search_position: str):
    """
    Вспомогательная функция: делает JOIN с таблицей должностей
    и применяет поиск по name и name_en.
    """
    pos = aliased(Position, name="pos")

    # JOIN с таблицей должностей
    query = query.join(pos, Employee.position_guid == pos.guid)

    search_term = f"%{search_position}%"

    # Ищем совпадение в name или name_en
    query = query.where(
        or_(
            pos.name.ilike(search_term),
            pos.name_en.ilike(search_term),
        )
    )
    return query

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
        is_active: Optional[bool] = None,
        search_department: Optional[str] = None,
        search_position: Optional[str] = None
) -> Tuple[Sequence[Employee], int]:

    total = await get_employees_count(
        db, employee_id, last_name, first_name, middle_name,
        last_name_en, first_name_en, middle_name_en,
        department_guid, position_guid, is_active, search_department, search_position
    )

    skip = (page - 1) * page_size

    # Подгружаем иерархию через selectinload (до 4 уровней)
    query = (
        select(Employee)
        .options(
            selectinload(Employee.position),
            selectinload(Employee.group).options(
                selectinload(ZupDepartment.parent).options(
                    selectinload(ZupDepartment.parent).options(
                        selectinload(ZupDepartment.parent)
                    )
                )
            )
        )
    )

    if employee_id:
        # query = query.where(Employee.employee_id == employee_id)
        query = query.where(Employee.employee_id.ilike(f"%{employee_id}%"))
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
    if search_position:
        query = _apply_position_search(query, search_position)
    if is_active is not None:
        if is_active:
            query = query.where(Employee.dismissal_date.is_(None))
        else:
            query = query.where(Employee.dismissal_date.isnot(None))
    # Применяем поиск по подразделениям
    if search_department:
        query = _apply_department_search(query, search_department)

    query = query.order_by(Employee.employee_id).offset(skip).limit(page_size)

    result = await db.execute(query)
    employees = result.scalars().unique().all()

    # Извлекаем иерархию из уже подгруженных объектов (без N+1 запросов!)
    for emp in employees:
        hierarchy_chain = []
        current = emp.group  # Непосредственное подразделение сотрудника

        # Безопасный обход иерархии без ленивой загрузки
        while current is not None:
            hierarchy_chain.append(current)

            # Проверяем, достигли ли мы корня (нулевой parent_guid)
            if not current.parent_guid or current.parent_guid == "00000000-0000-0000-0000-000000000000":
                break

            # Проверяем, загружен ли parent через SQLAlchemy Inspector
            # Это предотвращает попытку ленивой загрузки
            insp = inspect(current)
            parent_attr = insp.attrs.get('parent')

            if parent_attr is None or parent_attr.loaded_value is None:
                # Parent не загружен - прекращаем обход
                break

            current = parent_attr.loaded_value

        # Реверсируем цепочку: [0] — корень (Общество), [1] — подразделение сотрудника
        hierarchy_chain.reverse()

        # Заполняем поля строго сверху вниз без пробелов
        emp.society = hierarchy_chain[0] if len(hierarchy_chain) >= 1 else None
        emp.department = hierarchy_chain[1] if len(hierarchy_chain) >= 2 else None
        emp.division = hierarchy_chain[2] if len(hierarchy_chain) >= 3 else None
        emp.group = hierarchy_chain[3] if len(hierarchy_chain) >= 4 else None

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

async def bulk_upsert_employees(db: AsyncSession, employees: List[Dict[str, Any]]) -> int:
    """
    Пакетная вставка/обновление сотрудников с защитой от превышения лимита asyncpg.
    Разбивает данные на чанки по 1000 записей.
    """
    if not employees:
        return 0

    chunk_size = 1000  # 1000 * 16 полей = 16000 параметров (безопасно < 32767)
    total_upserted = 0

    for i in range(0, len(employees), chunk_size):
        chunk = employees[i:i + chunk_size]

        stmt = insert(Employee).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=['guid'],
            set_={
                'guid_person': stmt.excluded.guid_person,
                'employee_id': stmt.excluded.employee_id,
                'last_name': stmt.excluded.last_name,
                'first_name': stmt.excluded.first_name,
                'middle_name': stmt.excluded.middle_name,
                'last_name_en': stmt.excluded.last_name_en,
                'first_name_en': stmt.excluded.first_name_en,
                'middle_name_en': stmt.excluded.middle_name_en,
                'birth_date': stmt.excluded.birth_date,
                'employment_date': stmt.excluded.employment_date,
                'dismissal_date': stmt.excluded.dismissal_date,
                'phone': stmt.excluded.phone,
                'email': stmt.excluded.email,
                'position_guid': stmt.excluded.position_guid,
                'department_guid': stmt.excluded.department_guid,
                'updated_at': func.now()
            }
        )

        await db.execute(stmt)
        total_upserted += len(chunk)
        logger.debug(f"Обработан чанк сотрудников: {i + len(chunk)} из {len(employees)}")

    await db.commit()
    return total_upserted