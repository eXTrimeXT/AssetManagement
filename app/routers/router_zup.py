import logging
import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database.connection import get_db
from app.schemas.zup.EmployeeSchemas import EmployeeResponse, EmployeeShortResponse, EmployeeCommentUpdate, \
    EmployeePersonalResponse
from app.schemas.zup.PositionSchemas import PositionResponse
from app.schemas.zup.DepartmentSchemas import WorkplaceResponse, DepartmentDivisionGroupResponse
from app.schemas.zup.ManagerSchemas import ManagerResponse
from app.database.zup.crud_zup_employees import get_employees_list, get_employee_by_guid, get_employee_by_id, \
    update_employee_comment
from app.database.zup.crud_zup_positions import get_positions_list, get_position_by_guid
from app.database.zup.crud_zup_departments import get_departments_list, get_hierarchy_departments
from app.database.zup.crud_zup_managers import get_managers_list
from app.services.zup.zup_integration import sync_all_data, sync_employee_data
from app.services.auth.auth_service import require_authorized_user
from app.schemas.PaginationResponse import PaginatedResponse

logger = logging.getLogger(__name__)

router_zup = APIRouter(prefix="/zup", tags=["1С-ЗУП Integration"])

@router_zup.post(
    "/sync",
    summary="Синхронизировать все данные из 1С-ЗУП / Sync All Data from 1C-ZUP",
    description=(
            "RU: Универсальный эндпоинт для заполнения/обновления всех таблиц из 1С-ЗУП. "
            "Синхронизирует: подразделения, должности, сотрудников, руководителей, назначения, отчёты. "
            "Возвращает статистику по выполненной синхронизации. "
            "В случае ошибки возвращается HTTP 500 с описанием проблемы.\n\n"
            "EN: Universal endpoint for populating/updating all tables from 1C-ZUP. "
            "Synchronizes: departments, positions, employees, managers, assignments, reports. "
            "Returns statistics on the performed synchronization. "
            "In case of an error, HTTP 500 is returned with a description of the issue."
    )
)
async def sync_zup_data(
        db: AsyncSession = Depends(get_db),
        # current_user=Depends(require_authorized_user)
):
    """
    Универсальный эндпоинт для заполнения/обновления всех таблиц из 1С-ЗУП.
    Синхронизирует: подразделения, должности, сотрудников, руководителей, назначения, отчёты.
    """
    try:
        stats = await sync_all_data(db)
        return {
            "success": True,
            "message": "Синхронизация завершена успешно",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Ошибка синхронизации: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка синхронизации: {str(e)}")


@router_zup.post(
    "/sync-employee",
    summary="Синхронизировать данные сотрудников из 1С-ЗУП / Sync Employee Data from 1C-ZUP",
    description=(
            "RU: Эндпоинт для заполнения/обновления данных сотрудников из 1С-ЗУП. "
            "Синхронизирует: подразделения, должности, сотрудников, руководителей, назначения, отчёты. "
            "Возвращает статистику по выполненной синхронизации. "
            "Требуется авторизация пользователя. "
            "В случае ошибки возвращается HTTP 500 с описанием проблемы.\n\n"
            "EN: Endpoint for populating/updating employee data from 1C-ZUP. "
            "Synchronizes: departments, positions, employees, managers, assignments, reports. "
            "Returns statistics on the performed synchronization. "
            "User authorization is required. "
            "In case of an error, HTTP 500 is returned with a description of the issue."
    )
)
async def sync_zup_employee_data(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Универсальный эндпоинт для заполнения/обновления всех таблиц из 1С-ЗУП.
    Синхронизирует: подразделения, должности, сотрудников, руководителей, назначения, отчёты.
    """
    try:
        stats = await sync_employee_data(db)
        return {
            "success": True,
            "message": "Синхронизация завершена успешно",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Ошибка синхронизации: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка синхронизации: {str(e)}")


@router_zup.get(
    "/employees",
    response_model=PaginatedResponse[EmployeeShortResponse],
    summary="Получить список сотрудников / Get Employees List",
    description=(
            "RU: Возвращает пагинированный список сотрудников с поддержкой расширенной фильтрации: "
            "по табельному номеру (`employee_id`), поиску по ФИО в любом порядке (`search_name`), "
            "статусу активности (`is_active`), поиску по подразделению (`search_department`) "
            "и поиску по должности на русском или английском языке (`search_position`). "
            "Поддерживает пагинацию через параметры `page` и `page_size`. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns a paginated list of employees with advanced filtering support: "
            "by employee ID (`employee_id`), full name search in any order (`search_name`), "
            "active status (`is_active`), department search (`search_department`), "
            "and position search in Russian or English (`search_position`). "
            "Supports pagination via `page` and `page_size` parameters. "
            "User authorization is required."
    )
)
async def get_employees(
        page: int = Query(1, ge=1, description="Номер страницы (начинается с 1)"),
        page_size: int = Query(50, ge=1, le=100, description="Размер страницы"),
        employee_id: Optional[str] = Query(None, description="Табельный номер"),
        search_name: Optional[str] = Query(None, max_length=100, description="Поиск по ФИО в любом порядке (например: 'Иванов Иван' или 'Иван Иванов')"),
        is_active: Optional[bool] = Query(None, description="Только действующие сотрудники"),
        search_department: Optional[str] = Query(None, description="Поиск по названию или краткому названию подразделения (общество, департамент, отдел, группа)"),
        search_position: Optional[str] = Query(None, description="Поиск по названию на англ. или рус. языке"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Получить страницу сотрудников с фильтрацией.
    - **page**: номер страницы (начинается с 1)
    - **page_size**: количество записей на странице (по умолчанию 50)
    """

    employees, total = await get_employees_list(
        db=db,
        page=page,
        page_size=page_size,
        employee_id=employee_id,
        search_name=search_name,
        is_active=is_active,
        search_department=search_department,
        search_position=search_position
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse(
        items=list(employees),
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1
    )


@router_zup.get(
    "/employees/guid/{guid}",
    response_model=EmployeeResponse,
    summary="Получить сотрудника по GUID / Get Employee by GUID",
    description=(
            "RU: Возвращает полную информацию о сотруднике по его уникальному GUID. "
            "Если сотрудник не найден — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns full information about an employee by their unique GUID. "
            "If the employee is not found, a 404 error is returned. "
            "User authorization is required."
    )
)
async def get_employee(
        guid: str,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить полную информацию о сотруднике по GUID"""
    employee = await get_employee_by_guid(db, guid)
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return employee


@router_zup.get(
    "/employees/me",
    response_model=EmployeePersonalResponse,
    summary="Получить данные текущего сотрудника / Get Current Employee Data",
    description=(
            "RU: Возвращает полную информацию о текущем авторизованном сотруднике, "
            "включая иерархию подразделений (группа, отдел, департамент, общество) "
            "и данные о должности. Определяется по `employee_id` текущего пользователя. "
            "Если сотрудник не найден — возвращается ошибка 404. "
            "Требуется авторизация.\n\n"
            "EN: Returns full information about the current authenticated employee, "
            "including the department hierarchy (group, division, department, society) "
            "and position data. Determined by the `employee_id` of the current user. "
            "If the employee is not found, a 404 error is returned. "
            "Authorization is required."
    )
)
async def get_employee(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    employee = await get_employee_by_id(db, current_user.employee_id)

    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    # Создаём базовый response без проблемных полей
    response = EmployeePersonalResponse.model_validate(employee)

    # Загружаем иерархию отдельно
    if employee.department_guid:
        hierarchy = await get_hierarchy_departments(db, employee.department_guid)
        if hierarchy:
            response.group = hierarchy.group
            response.division = hierarchy.division
            response.department = hierarchy.department
            response.society = hierarchy.society
            # ... остальные поля иерархии

    # Загружаем должность отдельно
    if employee.position_guid:
        position = await get_position_by_guid(db, employee.position_guid)
        if position:
            response.position = PositionResponse.model_validate(position)

    return response


@router_zup.get(
    "/employees/id/{id}",
    response_model=EmployeeResponse,
    summary="Получить сотрудника по ID / Get Employee by ID",
    description=(
            "RU: Возвращает полную информацию о сотруднике по его табельному номеру (ID). "
            "Если сотрудник не найден — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns full information about an employee by their employee ID. "
            "If the employee is not found, a 404 error is returned. "
            "User authorization is required."
    )
)
async def get_employee(
        id: str,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить полную информацию о сотруднике по ID"""
    employee = await get_employee_by_id(db, id)
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return employee


@router_zup.patch(
    "/employees/{employee_id}/comment",
    response_model=EmployeeResponse,
    summary="Обновить комментарий сотрудника / Update Employee Comment",
    description=(
            "RU: Обновляет только поле `comment` для указанного сотрудника по его `employee_id`. "
            "Если сотрудник не найден — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Updates only the `comment` field for the specified employee by their `employee_id`. "
            "If the employee is not found, a 404 error is returned. "
            "User authorization is required."
    )
)
async def update_employee_comment_endpoint(
        employee_id: str,
        data: EmployeeCommentUpdate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Обновить только поле comment для сотрудника по employee_id.
    """
    employee = await update_employee_comment(db, employee_id, data.comment)
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return employee


@router_zup.get(
    "/positions",
    response_model=List[PositionResponse],
    summary="Получить список должностей / Get Positions List",
    description=(
            "RU: Возвращает список должностей с поддержкой пагинации через параметры `skip` и `limit`. "
            "По умолчанию возвращается до 50 записей. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns a list of positions with pagination support via `skip` and `limit` parameters. "
            "By default, up to 50 records are returned. "
            "User authorization is required."
    )
)
async def get_positions(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить список должностей"""
    return await get_positions_list(db, skip, limit)


@router_zup.get(
    "/departments",
    response_model=List[WorkplaceResponse],
    summary="Получить список подразделений / Get Departments List",
    description=(
            "RU: Возвращает список подразделений с иерархией и поддержкой пагинации "
            "через параметры `skip` и `limit`. По умолчанию возвращается до 50 записей. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns a list of departments with hierarchy and pagination support "
            "via `skip` and `limit` parameters. By default, up to 50 records are returned. "
            "User authorization is required."
    )
)
async def get_departments(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить список подразделений с иерархией"""
    return await get_departments_list(db, skip, limit)


@router_zup.get(
    "/hierarchy-departments",
    response_model=DepartmentDivisionGroupResponse,
    summary="Получить иерархию подразделений / Get Departments Hierarchy",
    description=(
            "RU: Возвращает плоскую иерархию подразделений от группы до общества по GUID подразделения "
            "или строгому совпадению `short_name`. Структура ответа включает: `group` (группа, исходный GUID), "
            "`division` (отдел, parent от группы), `department` (департамент, parent от отдела), "
            "`society` (общество, parent от департамента). "
            "Если подразделение не найдено — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns a flat hierarchy of departments from group to society by department GUID "
            "or exact `short_name` match. The response structure includes: `group` (group, source GUID), "
            "`division` (division, parent of the group), `department` (department, parent of the division), "
            "`society` (society, parent of the department). "
            "If the department is not found, a 404 error is returned. "
            "User authorization is required."
    )
)
async def get_hierarchy_departments_endpoint(
        guid: Optional[str] = Query(None, description="GUID подразделения (группы)"),
        short_name: Optional[str] = Query(None, description="Поиск строго по short_name"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Получить плоскую иерархию подразделений от группы до общества.

    Возвращает структуру:
    - group: группа (исходный GUID)
    - division: отдел (parent от группы)
    - department: департамент (parent от отдела)
    - society: общество (parent от департамента, у него parent_guid == 00000000-...)
    """
    result = await get_hierarchy_departments(db, guid=guid, short_name=short_name)
    if result is None:
        raise HTTPException(status_code=404, detail="Подразделение не найдено")
    return result


@router_zup.get(
    "/managers",
    response_model=List[ManagerResponse],
    summary="Получить список связей руководитель-сотрудник / Get Manager-Employee Relations List",
    description=(
            "RU: Возвращает список связей между сотрудниками и их руководителями с поддержкой пагинации "
            "через параметры `skip` и `limit`. По умолчанию возвращается до 50 записей. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns a list of relations between employees and their managers with pagination support "
            "via `skip` and `limit` parameters. By default, up to 50 records are returned. "
            "User authorization is required."
    )
)
async def get_managers(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить список связей сотрудник-руководитель"""
    return await get_managers_list(db, skip, limit)