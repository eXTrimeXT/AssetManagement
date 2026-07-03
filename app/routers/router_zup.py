import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database.connection import get_db
from app.schemas.zup.employee_schemas import EmployeeResponse, EmployeeBase
from app.schemas.zup.position_schemas import PositionResponse
from app.schemas.zup.department_schemas import DepartmentResponse
from app.schemas.zup.manager_schemas import ManagerResponse
from app.schemas.zup.assignment_schemas import AssignmentResponse
from app.schemas.zup.report_schemas import ReportResponse
from app.database.zup.crud_zup_employees import get_employees_list, get_employee_by_guid
from app.database.zup.crud_zup_positions import get_positions_list
from app.database.zup.crud_zup_departments import get_departments_list
from app.database.zup.crud_zup_managers import get_managers_list
from app.database.zup.crud_zup_assignments import get_assignments_list
from app.database.zup.crud_zup_reports import get_reports_list
from app.services.zup.zup_integration import sync_all_data
# from app.services.auth.auth_service import require_authorized_user

logger = logging.getLogger(__name__)
router_zup = APIRouter(prefix="/zup", tags=["1С-ЗУП Integration"])


@router_zup.post("/sync", summary="Синхронизировать все данные из 1С-ЗУП")
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


@router_zup.get("/employees", response_model=List[EmployeeBase], summary="Получить список сотрудников")
async def get_employees(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        employee_id: Optional[str] = Query(None, description="Табельный номер"),
        last_name: Optional[str] = Query(None, description="Фамилия (рус)"),
        first_name: Optional[str] = Query(None, description="Имя (рус)"),
        last_name_en: Optional[str] = Query(None, description="Фамилия (англ)"),
        first_name_en: Optional[str] = Query(None, description="Имя (англ)"),
        department_guid: Optional[str] = Query(None, description="GUID подразделения"),
        position_guid: Optional[str] = Query(None, description="GUID должности"),
        is_active: Optional[bool] = Query(None, description="Только действующие сотрудники"),
        db: AsyncSession = Depends(get_db),
        # current_user=Depends(require_authorized_user)
):
    """Получить список сотрудников с фильтрацией"""
    employees = await get_employees_list(
        db=db,
        skip=skip,
        limit=limit,
        employee_id=employee_id,
        last_name=last_name,
        first_name=first_name,
        last_name_en=last_name_en,
        first_name_en=first_name_en,
        department_guid=department_guid,
        position_guid=position_guid,
        is_active=is_active
    )
    return employees


@router_zup.get("/employees/{guid}", response_model=EmployeeResponse, summary="Получить сотрудника по GUID")
async def get_employee(
        guid: str,
        db: AsyncSession = Depends(get_db),
        # current_user=Depends(require_authorized_user)
):
    """Получить полную информацию о сотруднике по GUID"""
    employee = await get_employee_by_guid(db, guid)
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return employee


@router_zup.get("/positions", response_model=List[PositionResponse], summary="Получить список должностей")
async def get_positions(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        # current_user=Depends(require_authorized_user)
):
    """Получить список должностей"""
    return await get_positions_list(db, skip, limit)


@router_zup.get("/departments", response_model=List[DepartmentResponse], summary="Получить список подразделений")
async def get_departments(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        # current_user=Depends(require_authorized_user)
):
    """Получить список подразделений с иерархией"""
    return await get_departments_list(db, skip, limit)


@router_zup.get("/managers", response_model=List[ManagerResponse], summary="Получить список связей руководитель-сотрудник")
async def get_managers(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        # current_user=Depends(require_authorized_user)
):
    """Получить список связей сотрудник-руководитель"""
    return await get_managers_list(db, skip, limit)


@router_zup.get("/assignments", response_model=List[AssignmentResponse], summary="Получить список назначений")
async def get_assignments(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        # current_user=Depends(require_authorized_user)
):
    """Получить историю кадровых назначений"""
    return await get_assignments_list(db, skip, limit)


@router_zup.get("/reports", response_model=ReportResponse, summary="Получить отчёт по присутствию")
async def get_reports(
        db: AsyncSession = Depends(get_db),
        # current_user=Depends(require_authorized_user)
):
    """Получить сводный отчёт по присутствию сотрудников"""
    reports = await get_reports_list(db)
    return {"attendance_data": reports}