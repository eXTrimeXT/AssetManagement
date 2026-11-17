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
    get_assignment_by_id, get_all_assignments, decline_assignment
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
    status_code=status.HTTP_200_OK,
    summary="Привязать актив к сотруднику / Assign Asset to Employee",
    description=(
            "RU: Назначает актив сотруднику. `asset_id` передаётся в теле запроса. "
            "Автоматически закрывает предыдущие активные назначения этого сотрудника на данный актив. "
            "Проверяет наличие права на запись (write) для типа актива.\n\n"
            "EN: Assigns an asset to an employee. The `asset_id` is passed in the request body. "
            "Automatically closes any previous active assignments of this employee to the same asset. "
            "Checks for write permissions on the asset type."
    )
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
    summary="Получить все привязки (с фильтрами) / Get All Assignments (with filters)",
    description=(
            "RU: Возвращает список привязок активов с поддержкой фильтрации по `asset_id`, `employee_id` "
            "и параметром `active_only` для отображения только активных привязок. "
            "Если не указаны фильтры — возвращаются все привязки.\n\n"
            "EN: Returns a list of asset assignments with filtering support by `asset_id`, `employee_id`, "
            "and the `active_only` parameter to display only active assignments. "
            "If no filters are specified, all assignments are returned."
    )
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

@router_asset_assignments.get(
    "/{asset_id}/assignments",
    response_model=List[AssetAssignmentResponse],
    summary="Получить привязки конкретного актива / Get Assignments of a Specific Asset",
    description=(
            "RU: Возвращает список всех привязок указанного актива по его `asset_id`. "
            "Поддерживает параметр `active_only` для отображения только активных привязок.\n\n"
            "EN: Returns a list of all assignments for the specified asset by its `asset_id`. "
            "Supports the `active_only` parameter to display only active assignments."
    )
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
    summary="Получить привязки конкретного сотрудника / Get Assignments of a Specific Employee",
    description=(
            "RU: Возвращает список всех привязок указанного сотрудника по его табельному номеру `employee_id`. "
            "Поддерживает параметр `active_only` для отображения только активных привязок.\n\n"
            "EN: Returns a list of all assignments for the specified employee by their employee ID `employee_id`. "
            "Supports the `active_only` parameter to display only active assignments."
    )
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
    summary="Закрыть привязку / Close Assignment",
    description=(
            "RU: Закрывает активную привязку актива к сотруднику, устанавливая `end_date` равным текущей дате. "
            "Инициатор закрытия (`closed_by`) фиксируется как текущий пользователь. "
            "Отправляется уведомление администратору. Проверяется право на запись (write) для типа актива.\n\n"
            "EN: Closes an active asset assignment by setting `end_date` to the current date. "
            "The initiator (`closed_by`) is recorded as the current user. "
            "A notification is sent to the administrator. Write permission is checked for the asset type."
    )
)
async def endpoint_close_assignment_endpoint(
        assignment_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Закрыть активную привязку (установить end_date = сегодня) и отправить уведомление админу"""
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

@router_asset_assignments.post(
    "/assignments/{asset_id}/decline",
    response_model=AssetAssignmentResponse,
    summary="Отказаться от актива / Decline Asset Assignment",
    description=(
            "RU: Позволяет сотруднику отказаться от привязанного к нему актива. "
            "Привязка закрывается (устанавливается `end_date` = сегодня), "
            "инициатору назначения (`assigned_by`) отправляется уведомление об отказе. "
            "Проверяется право на запись (write) для типа актива.\n\n"
            "EN: Allows an employee to decline an asset assigned to them. "
            "The assignment is closed (`end_date` is set to today), "
            "and the assignment initiator (`assigned_by`) receives a decline notification. "
            "Write permission is checked for the asset type."
    )
)
async def endpoint_decline_assignment(
        asset_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Сотрудник отказывается от привязанного к нему актива.
    Привязка закрывается (end_date = сегодня), инициатору (assigned_by)
    отправляется уведомление об отказе.
    """
    # Проверяем существование актива (опционально, но полезно для валидации)
    asset = await get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")

    if asset:
        await check_asset_permission(db, request, asset.asset_type_id, "write")

    # Пытаемся закрыть привязку
    assignment = await decline_assignment(db, asset_id, current_user.employee_id)

    if not assignment:
        raise HTTPException(
            status_code=404,
            detail="Активная привязка к данному активу для текущего сотрудника не найдена"
        )

    return assignment

@router_asset_assignments.delete(
    "/assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить привязку / Delete Assignment",
    description=(
            "RU: Удаляет привязку актива. Удаление разрешено только для неактивных привязок "
            "(у которых уже установлен `end_date`). Для активных привязок необходимо сначала закрыть их. "
            "Проверяется право на запись (write) для типа актива.\n\n"
            "EN: Deletes an asset assignment. Deletion is only allowed for inactive assignments "
            "(those with `end_date` already set). Active assignments must be closed first. "
            "Write permission is checked for the asset type."
    )
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

@router_asset_assignments.get(
    "/assignments/my-pc",
    response_model=list[PCDataResponse],
    summary="Получить данные ПК текущего пользователя / Get Current User's PC Data",
    description=(
            "RU: Возвращает список записей о ПК, связанных с текущим авторизованным пользователем "
            "по его `active_directory_login`. Поддерживает пагинацию через параметры `skip` и `limit`. "
            "Требуется право на чтение (read) для типа актива `computer` или сущности `pc_data`.\n\n"
            "EN: Returns a list of PC records associated with the current authenticated user "
            "by their `active_directory_login`. Supports pagination via `skip` and `limit` parameters. "
            "Requires read permission for the `computer` asset type or the `pc_data` entity."
    )
)
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
    summary="Получить текущие активы пользователя / Get Current User's Active Assets",
    description=(
            "RU: Возвращает список всех текущих (активных) активов, привязанных к авторизованному сотруднику. "
            "Определяется по `employee_id` текущего пользователя.\n\n"
            "EN: Returns a list of all current (active) assets assigned to the authenticated employee. "
            "Determined by the `employee_id` of the current user."
    )
)
async def endpoint_get_my_active_assets(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить все текущие (активные) активы авторизованного сотрудника."""
    return await get_active_assets_by_employee(db, current_user.employee_id)