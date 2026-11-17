from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.schemas.assets.AssetTransferSchemas import (
    AssetTransferRequest,
    TransferActionRequest,
    AssetTransferResponse,
    AssetTransferRespondResponse,
    AssetTransferCancelResponse, AssetTransferExistsResponse
)
from app.database.assets.crud_asset_transfer import (
    request_asset_transfer,
    respond_to_asset_transfer,
    cancel_asset_transfer, check_pending_transfer_exists, get_transfers_list
)
from app.services.auth.auth_service import require_authorized_user
from app.schemas.PaginationResponse import PaginatedResponse

router_asset_transfer = APIRouter(prefix="/assets/transfers", tags=["Asset Transfers"])


@router_asset_transfer.get(
    "/",
    response_model=PaginatedResponse,
    summary="Получить список передач активов / Get Asset Transfers List",
    description=(
            "RU: Возвращает пагинированный список запросов на передачу активов с поддержкой фильтрации: "
            "по `asset_id`, инициатору (`initiator_id`), получателю (`target_employee_id`), "
            "параметрам `only_my` (только мои передачи) и `only_active` (только активные запросы). "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns a paginated list of asset transfer requests with filtering support: "
            "by `asset_id`, initiator (`initiator_id`), target employee (`target_employee_id`), "
            "and the `only_my` (only my transfers) and `only_active` (only active requests) parameters. "
            "User authorization is required."
    )
)
async def get_transfers(
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=100),
        asset_id: Optional[int] = Query(None),
        initiator_id: Optional[str] = Query(None),
        target_employee_id: Optional[str] = Query(None),
        only_my: Optional[bool] = Query(False),
        only_active: Optional[bool] = Query(False),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    result = await get_transfers_list(
        db=db,
        page=page,
        page_size=page_size,
        asset_id=asset_id,
        initiator_id=initiator_id,
        target_employee_id=target_employee_id,
        only_my=only_my,
        employee_id=current_user.employee_id,
        only_active=only_active
    )
    return PaginatedResponse(**result)

@router_asset_transfer.post(
    "/request/",
    response_model=AssetTransferResponse,
    summary="Создать запрос на передачу актива / Create Asset Transfer Request",
    description=(
            "RU: Создает запрос на передачу актива другому сотруднику. "
            "Если указан `asset_id` — передается существующий локальный актив. "
            "Если указан `material_id` — актив сначала создается локально из данных SAP. "
            "Автоматически создается уведомление для получателя. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Creates a request to transfer an asset to another employee. "
            "If `asset_id` is specified, an existing local asset is transferred. "
            "If `material_id` is specified, the asset is first created locally from SAP data. "
            "A notification is automatically created for the recipient. "
            "User authorization is required."
    )
)
async def create_transfer_request(
        request: AssetTransferRequest,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Создать запрос на передачу актива.
    - Если указан `asset_id` — передается существующий локальный актив
    - Если указан `material_id` — актив сначала создается локально из SAP данных
    - Создается уведомление для получателя
    """
    try:
        response = await request_asset_transfer(
            db=db,
            request=request,
            initiator_id=current_user.employee_id
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e.detail))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании запроса: {str(e)}"
        )


@router_asset_transfer.post(
    "/check-request",
    response_model=AssetTransferExistsResponse,
    summary="Проверить наличие запроса на передачу актива / Check Asset Transfer Request Existence",
    description=(
            "RU: Проверяет наличие активного запроса на передачу указанного актива для текущего пользователя. "
            "Возвращает информацию о направлении передачи (входящий/исходящий). "
            "Если запрос не найден или доступ не разрешен — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Checks for an active transfer request for the specified asset for the current user. "
            "Returns information about the transfer direction (incoming/outgoing). "
            "If the request is not found or access is not allowed, a 404 error is returned. "
            "User authorization is required."
    )
)
async def check_transfer_exists(
        asset_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    response = await check_pending_transfer_exists(db, asset_id, current_user.employee_id)
    if response.direction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Доступ не разрешен"
        )
    return response


@router_asset_transfer.post(
    "/{transfer_id}/respond",
    response_model=AssetTransferRespondResponse,
    summary="Ответить на запрос передачи актива / Respond to Asset Transfer Request",
    description=(
            "RU: Позволяет получателю ответить на запрос передачи актива. "
            "Доступные действия: `action=\"accept\"` — принять актив, `action=\"decline\"` — отклонить передачу. "
            "Может содержать необязательный комментарий. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Allows the recipient to respond to an asset transfer request. "
            "Available actions: `action=\"accept\"` — accept the asset, `action=\"decline\"` — decline the transfer. "
            "May include an optional comment. "
            "User authorization is required."
    )
)
async def respond_transfer_request(
        transfer_id: int,
        action_request: TransferActionRequest,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Ответить на запрос передачи актива.
    - `action="accept"` — принять актив
    - `action="decline"` — отклонить передачу
    """
    try:
        response = await respond_to_asset_transfer(
            db=db,
            transfer_id=transfer_id,
            action=action_request.action,
            responder_id=current_user.employee_id,
            comment=action_request.comment
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обработке ответа: {str(e)}"
        )

@router_asset_transfer.post(
    "/{transfer_id}/cancel",
    response_model=AssetTransferCancelResponse,
    summary="Отменить запрос на передачу актива / Cancel Asset Transfer Request",
    description=(
            "RU: Отменяет активный запрос на передачу актива. "
            "Доступно только инициатору запроса (`initiator_id` должен совпадать с текущим пользователем). "
            "При попытке отмены чужого запроса возвращается ошибка. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Cancels an active asset transfer request. "
            "Only available to the request initiator (`initiator_id` must match the current user). "
            "An error is returned if attempting to cancel someone else's request. "
            "User authorization is required."
    )
)
async def cancel_transfer_request(
        transfer_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Отменить запрос на передачу актива (доступно только инициатору).
    """
    try:
        response = await cancel_asset_transfer(
            db=db,
            transfer_id=transfer_id,
            initiator_id=current_user.employee_id
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при отмене заявки: {str(e)}"
        )