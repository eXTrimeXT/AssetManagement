import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database.connection import get_db
from app.database.assets.crud_asset_write_off import (
    create_write_off_request,
    get_write_off_by_id,
    get_write_offs_list,
    approve_write_off,
    reject_write_off,
)
from app.database.assets.crud_asset import get_asset_by_id
from app.schemas.assets.AssetWriteOffSchemas import (
    WriteOffRequest,
    WriteOffResponse,
    WriteOffRejectRequest,
    WriteOffListResponse,
)
from app.services.auth.auth_service import (
    require_authorized_user,
    get_token_from_request,
    check_assets_is_admin,
)
from app.services.auth.permission_checker import check_asset_permission

logger = logging.getLogger(__name__)

router_asset_write_off = APIRouter(prefix="/write-off", tags=["Asset Write-Off"])


def _write_off_to_response(write_off) -> WriteOffResponse:
    """Преобразование модели в схему ответа."""
    asset = write_off.asset
    requester = write_off.requester

    requester_name = None
    if requester:
        parts = [p for p in [requester.last_name, requester.first_name, requester.middle_name] if p]
        requester_name = " ".join(parts) if parts else None

    return WriteOffResponse(
        write_off_id=write_off.write_off_id,
        asset_id=write_off.asset_id,
        reason=write_off.reason,
        write_off_type=write_off.write_off_type,
        requested_by=write_off.requested_by,
        requested_at=write_off.requested_at,
        approved_by=write_off.approved_by,
        approved_at=write_off.approved_at,
        reject_reason=write_off.reject_reason,
        status=write_off.status,
        asset_name=asset.name if asset else None,
        asset_inventory_id=asset.inventory_id if asset else None,
        requester_full_name=requester_name,
    )


@router_asset_write_off.post(
    "/assets/{asset_id}",
    response_model=WriteOffResponse,
    status_code=201,
    summary="Создать заявку на списание актива / Create Asset Write-Off Request",
    description=(
            "RU: Создает новую заявку на списание указанного актива. "
            "Принимает причину и тип списания в теле запроса. "
            "Проверяет наличие права на запись (`write`) для типа актива — "
            "при отсутствии прав возвращается ошибка 403. "
            "Если актив не найден — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Creates a new write-off request for the specified asset. "
            "Accepts the reason and write-off type in the request body. "
            "Checks for write permission (`write`) on the asset type — "
            "a 403 error is returned if permissions are missing. "
            "If the asset is not found, a 404 error is returned. "
            "User authorization is required."
    )
)
async def create_write_off(
        asset_id: int,
        data: WriteOffRequest,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Создать заявку на списание. Право `write` на тип актива обязательно."""
    asset = await get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")

    await check_asset_permission(db, request, asset.asset_type_id, "write")

    try:
        write_off = await create_write_off_request(
            db=db,
            asset_id=asset_id,
            data=data,
            requested_by=current_user.employee_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _write_off_to_response(write_off)


@router_asset_write_off.get(
    "/",
    response_model=WriteOffListResponse,
    summary="Получить список заявок на списание / Get Write-Off Requests List",
    description=(
            "RU: Возвращает пагинированный список заявок на списание активов с поддержкой фильтрации "
            "по статусу (`status`) и идентификатору актива (`asset_id`). "
            "Поддерживает пагинацию через параметры `page` и `page_size`. "
            "Каждая запись обогащена информацией об активе и ФИО заявителя. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns a paginated list of asset write-off requests with filtering support "
            "by status (`status`) and asset identifier (`asset_id`). "
            "Supports pagination via `page` and `page_size` parameters. "
            "Each record is enriched with asset information and the requester's full name. "
            "User authorization is required."
    )
)
async def list_write_offs(
        status: Optional[str] = Query(None, description="Фильтр по статусу"),
        asset_id: Optional[int] = Query(None, description="Фильтр по активу"),
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Получить список заявок с фильтрами."""
    items, total = await get_write_offs_list(
        db=db,
        status=status,
        asset_id=asset_id,
        page=page,
        page_size=page_size,
    )

    return WriteOffListResponse(
        items=[_write_off_to_response(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router_asset_write_off.get(
    "/{write_off_id}",
    response_model=WriteOffResponse,
    summary="Получить заявку на списание по ID / Get Write-Off Request by ID",
    description=(
            "RU: Возвращает подробную информацию о заявке на списание актива по её уникальному "
            "идентификатору `write_off_id`. "
            "Ответ содержит данные актива, заявителя, статус и причину списания. "
            "Если заявка не найдена — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns detailed information about an asset write-off request by its unique "
            "identifier `write_off_id`. "
            "The response contains asset data, requester information, status, and write-off reason. "
            "If the request is not found, a 404 error is returned. "
            "User authorization is required."
    )
)
async def get_write_off(
        write_off_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    write_off = await get_write_off_by_id(db, write_off_id)
    if not write_off:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return _write_off_to_response(write_off)


@router_asset_write_off.post(
    "/{write_off_id}/approve",
    response_model=WriteOffResponse,
    summary="Утвердить заявку на списание / Approve Write-Off Request",
    description=(
            "RU: Утверждает заявку на списание актива по её `write_off_id`. "
            "Предназначено для использования администратором активов "
            "(проверка через `check_assets_is_admin`, в текущей версии закомментирована). "
            "Инициатор утверждения фиксируется как текущий пользователь. "
            "При попытке утверждения уже обработанной заявки возвращается ошибка 400. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Approves an asset write-off request by its `write_off_id`. "
            "Intended for use by the asset administrator "
            "(check via `check_assets_is_admin`, currently commented out). "
            "The approval initiator is recorded as the current user. "
            "If attempting to approve an already processed request, a 400 error is returned. "
            "User authorization is required."
    )
)
async def approve(
        write_off_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Утвердить заявку. Только админ активов."""
    token = await get_token_from_request(request)
    # if not check_assets_is_admin(token):
    #     raise HTTPException(status_code=403, detail="Только админ может утверждать списание")

    try:
        write_off = await approve_write_off(
            db=db,
            write_off_id=write_off_id,
            approved_by=current_user.employee_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _write_off_to_response(write_off)


@router_asset_write_off.post(
    "/{write_off_id}/reject",
    response_model=WriteOffResponse,
    summary="Отклонить заявку на списание / Reject Write-Off Request",
    description=(
            "RU: Отклоняет заявку на списание актива по её `write_off_id`. "
            "Требует обязательного указания причины отклонения в теле запроса (`reject_reason`). "
            "Предназначено для использования администратором активов "
            "(проверка через `check_assets_is_admin`, в текущей версии закомментирована). "
            "Инициатор отклонения фиксируется как текущий пользователь. "
            "При попытке отклонения уже обработанной заявки возвращается ошибка 400. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Rejects an asset write-off request by its `write_off_id`. "
            "Requires a mandatory rejection reason in the request body (`reject_reason`). "
            "Intended for use by the asset administrator "
            "(check via `check_assets_is_admin`, currently commented out). "
            "The rejection initiator is recorded as the current user. "
            "If attempting to reject an already processed request, a 400 error is returned. "
            "User authorization is required."
    )
)
async def reject(
        write_off_id: int,
        data: WriteOffRejectRequest,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Отклонить заявку. Только админ активов."""
    token = await get_token_from_request(request)
    # if not check_assets_is_admin(token):
    #     raise HTTPException(status_code=403, detail="Только админ может отклонять списание")

    try:
        write_off = await reject_write_off(
            db=db,
            write_off_id=write_off_id,
            approved_by=current_user.employee_id,
            data=data,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _write_off_to_response(write_off)