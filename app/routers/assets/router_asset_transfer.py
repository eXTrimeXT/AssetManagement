from fastapi import APIRouter, Depends, HTTPException, status
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
    cancel_asset_transfer, check_pending_transfer_exists
)
from app.services.auth.auth_service import require_authorized_user

router_asset_transfer = APIRouter(prefix="/assets/transfers", tags=["Asset Transfers"])

@router_asset_transfer.post(
    "/request",
    response_model=AssetTransferResponse,
    summary="Создать запрос на передачу актива"
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании запроса: {str(e)}"
        )


@router_asset_transfer.post(
    "/check-request",
    response_model=AssetTransferExistsResponse,
    summary="Проверяем есть ли у нас запрос на передачу актива"
)
async def check_transfer_exists(
        asset_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    response = await check_pending_transfer_exists(db, asset_id)
    return response


@router_asset_transfer.post(
    "/{transfer_id}/respond",
    response_model=AssetTransferRespondResponse,
    summary="Ответить на запрос передачи актива (принять или отклонить)"
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
    summary="Отменить запрос на передачу актива"
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