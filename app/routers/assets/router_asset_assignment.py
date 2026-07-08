import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database.connection import get_db
from app.database.assets.asset_assignment import (
    create_assignment,
    get_assignments_by_asset,
    get_assignments_by_employee,
    delete_assignment,
    close_assignment,
    get_assignment_by_id
)
from app.database.assets import get_asset_by_id

from app.schemas.assets.asset_assignment import (
    AssetAssignmentCreate,
    AssetAssignmentResponse
)
from app.services.auth.auth_service import require_authorized_user
from app.services.auth.permission_checker import check_permission

logger = logging.getLogger(__name__)
router_asset_assignments = APIRouter(prefix="/assets", tags=["Asset Assignments"])


@router_asset_assignments.post("/{asset_id}/assignments", response_model=AssetAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_asset_to_employee(
        asset_id: int,
        data: AssetAssignmentCreate,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Назначить актив сотруднику.
    Автоматически закрывает все предыдущие активные назначения этого сотрудника на этот актив.
    """
    # Проверяем право write на актив (через тип актива)
    asset = await get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")

    if asset.model and asset.model.asset_class and asset.model.asset_class.asset_type:
        en_name = asset.model.asset_class.asset_type.en_name
        has_perm = await check_permission(request, en_name, "write")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'write' на тип актива '{en_name}'"
            )

    return await create_assignment(db, asset_id, data, current_user.employee_id)


@router_asset_assignments.get("/{asset_id}/assignments", response_model=List[AssetAssignmentResponse])
async def get_asset_assignments(
        asset_id: int,
        active_only: bool = Query(False, description="Только активные назначения"),
        request: Request = None,
        db: AsyncSession = Depends(get_db),
        # current_user=Depends(require_authorized_user)
):
    """
    Получить все назначения актива (историю и текущие).
    """
    # Проверяем право read на актив
    asset = await get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")

    if asset.model and asset.model.asset_class and asset.model.asset_class.asset_type:
        en_name = asset.model.asset_class.asset_type.en_name
        has_perm = await check_permission(request, en_name, "read")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'read' на тип актива '{en_name}'"
            )

    return await get_assignments_by_asset(db, asset_id, active_only)


@router_asset_assignments.get("/employees/{employee_id}/assignments", response_model=List[AssetAssignmentResponse])
async def get_employee_assignments(
        employee_id: str,
        active_only: bool = Query(False, description="Только активные назначения"),
        db: AsyncSession = Depends(get_db),
        # current_user=Depends(require_authorized_user)
):
    """
    Получить все назначения сотрудника (все его активы).
    """
    return await get_assignments_by_employee(db, employee_id, active_only)


@router_asset_assignments.post("/assignments/{assignment_id}/close", response_model=AssetAssignmentResponse)
async def close_assignment_endpoint(
        assignment_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        # current_user=Depends(require_authorized_user)
):
    """
    Закрыть активное назначение (установить end_date = сегодня).
    """
    assignment = await get_assignment_by_id(db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Назначение не найдено")

    # Проверяем право write на актив
    asset = await get_asset_by_id(db, assignment.asset_id)
    if asset and asset.model and asset.model.asset_class and asset.model.asset_class.asset_type:
        en_name = asset.model.asset_class.asset_type.en_name
        has_perm = await check_permission(request, en_name, "write")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'write' на тип актива '{en_name}'"
            )

    closed = await close_assignment(db, assignment_id)
    return closed


@router_asset_assignments.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment_endpoint(
        assignment_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        # current_user=Depends(require_authorized_user)
):
    """
    Удалить назначение (только неактивные, у которых end_date != NULL).
    """
    assignment = await get_assignment_by_id(db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Назначение не найдено")

    # Нельзя удалить активное назначение
    if assignment.end_date is None:
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить активное назначение. Сначала закройте его."
        )

    # Проверяем право write на актив
    asset = await get_asset_by_id(db, assignment.asset_id)
    if asset and asset.model and asset.model.asset_class and asset.model.asset_class.asset_type:
        en_name = asset.model.asset_class.asset_type.en_name
        has_perm = await check_permission(request, en_name, "write")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'write' на тип актива '{en_name}'"
            )

    success = await delete_assignment(db, assignment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Назначение не найдено")