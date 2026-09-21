from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.schemas.assets.AssetTransferSchemas import AssetTransferRequest, TransferActionRequest
from app.database.assets.crud_asset_transfer import request_asset_transfer, respond_to_asset_transfer
from app.services.auth.auth_service import require_authorized_user

router_asset_transfer = APIRouter(prefix="/assets/transfers", tags=["Asset Transfers"])

@router_asset_transfer.post(
    "/request",
    summary="Запросить передачу актива другому пользователю"
)
async def create_transfer_request(
        request: AssetTransferRequest,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    try:
        notification = await request_asset_transfer(
            db=db,
            request=request,
            initiator_id=current_user.employee_id
        )
        return {"message": "Запрос на передачу отправлен", "notification_id": notification.notification_id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ошибка при создании запроса")

@router_asset_transfer.post(
    "/{notification_id}/respond",
    summary="Ответить на запрос передачи актива (принять или отклонить)"
)
async def respond_transfer_request(
        notification_id: int,
        action_request: TransferActionRequest,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    try:
        result = await respond_to_asset_transfer(
            db=db,
            notification_id=notification_id,
            action=action_request.action,
            responder_id=current_user.employee_id,
            comment=action_request.comment
        )
        return {"message": result["message"]}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ошибка при обработке ответа")