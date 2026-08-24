import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database.connection import get_db
from app.database.assets.crud_asset_assignment import (
    create_assignment,
    get_assignments_by_asset,
    get_assignments_by_employee,
    delete_assignment,
    close_assignment,
    get_assignment_by_id, get_all_assignments
)
from app.database.assets.crud_asset import get_asset_by_id, get_active_assets_by_employee
from app.database.crud_pc_data import get_all_pc_data
from app.schemas.assets.AssetAssignmentSchemas import (
    AssetAssignmentCreate,
    AssetAssignmentResponse
)
from app.services.auth.auth_service import require_authorized_user
from app.services.auth.permission_checker import check_asset_permission, check_permission
from app.schemas.assets.AssetSchemas import AssetResponse
from app.schemas.pc_data.PcDataSchemas import PCDataResponse

logger = logging.getLogger(__name__)
router_asset_assignments = APIRouter(prefix="/assets", tags=["Asset Assignments"])


@router_asset_assignments.post(
    "/assignments",
    response_model=AssetAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Привязать актив к сотруднику"
)
async def endpoint_assign_asset_to_employee(
        data: AssetAssignmentCreate,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Назначить актив сотруднику.
    asset_id передаётся в теле запроса.
    Автоматически закрывает предыдущие активные назначения этого сотрудника на этот актив.
    """
    asset = await get_asset_by_id(db, data.asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")

    await check_asset_permission(db, request, asset.asset_type_id, "write")

    return await create_assignment(db, data, current_user.employee_id)


@router_asset_assignments.get(
    "/assignments",
    response_model=List[AssetAssignmentResponse],
    summary="Получить все привязки (с фильтрами)"
)
async def endpoint_get_all_assignments(
        asset_id: Optional[int] = Query(None, description="Фильтр по ID актива"),
        employee_id: Optional[str] = Query(None, description="Фильтр по табельному номеру"),
        active_only: bool = Query(False, description="Только активные привязки"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить привязки с фильтрацией по asset_id и/или employee_id."""
    if asset_id is not None:
        return await get_assignments_by_asset(db, asset_id, active_only)
    if employee_id is not None:
        return await get_assignments_by_employee(db, employee_id, active_only)

    return await get_all_assignments(db, active_only)
    # raise HTTPException(
    #     status_code=400,
    #     detail="Укажите хотя бы один фильтр: asset_id или employee_id"
    # )


@router_asset_assignments.get(
    "/{asset_id}/assignments",
    response_model=List[AssetAssignmentResponse],
    summary="Получить привязки конкретного актива"
)
async def endpoint_get_asset_assignments(
        asset_id: int,
        active_only: bool = Query(False, description="Только активные привязки"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить все привязки конкретного актива."""
    return await get_assignments_by_asset(db, asset_id, active_only)


@router_asset_assignments.get(
    "/employees/{employee_id}/assignments",
    response_model=List[AssetAssignmentResponse],
    summary="Получить привязки конкретного сотрудника"
)
async def endpoint_get_employee_assignments(
        employee_id: str,
        active_only: bool = Query(False, description="Только активные привязки"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить все привязки конкретного сотрудника."""
    return await get_assignments_by_employee(db, employee_id, active_only)


@router_asset_assignments.post(
    "/assignments/{assignment_id}/close",
    response_model=AssetAssignmentResponse,
    summary="Закрыть привязку"
)
async def endpoint_close_assignment_endpoint(
        assignment_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Закрыть активную привязку (установить end_date = сегодня)."""
    assignment = await get_assignment_by_id(db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Привязка не найдена")

    asset = await get_asset_by_id(db, assignment.asset_id)
    if asset:
        await check_asset_permission(db, request, asset.asset_type_id, "write")

    # === ПЕРЕДАЁМ current_user.employee_id как инициатора ===
    return await close_assignment(
        db=db,
        assignment_id=assignment_id,
        closed_by=current_user.employee_id,
    )


@router_asset_assignments.delete(
    "/assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить привязку"
)
async def endpoint_delete_assignment_endpoint(
        assignment_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Удалить привязку (только неактивные)."""
    assignment = await get_assignment_by_id(db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Привязка не найдена")

    if assignment.end_date is None:
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить активную привязку. Сначала закройте её."
        )

    asset = await get_asset_by_id(db, assignment.asset_id)
    if asset:
        await check_asset_permission(db, request, asset.asset_type_id, "write")

    success = await delete_assignment(db, assignment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Привязка не найдена")

@router_asset_assignments.get("/assignments/my-pc", response_model=list[PCDataResponse])
async def endpoint_endpoint_get_my_pc(
        request: Request,
        # username: Optional[str] = Query(None),
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    has_perm = await check_permission(request, "computer", "read")
    has_system_perm = await check_permission(request, "pc_data", "read")

    if not has_perm and not has_system_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'read' на тип актива 'computer'"
        )
    if current_user.active_directory_login is not None:
        return await get_all_pc_data(db, current_user.active_directory_login, skip, limit)
    raise HTTPException(
        status_code=404,
        detail=f"Ошибка данных пользователя, отсутствует active_directory_login!"
    )


@router_asset_assignments.get(
    "/assignments/me",
    response_model=List[AssetResponse],
    summary="Получить все текущие активы текущего пользователя"
)
async def endpoint_get_my_active_assets(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить все текущие (активные) активы авторизованного сотрудника."""
    return await get_active_assets_by_employee(db, current_user.employee_id)