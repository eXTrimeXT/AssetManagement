import logging
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.database.assets.crud_asset_confirmation import (
    create_confirmation_request,
    process_confirmation,
    get_confirmations_list,
    get_last_confirmation
)
from app.schemas.assets.AssetConfirmationSchemas import CreateConfirmationRequest, ConfirmAssetRequest, AssetConfirmationResponse
from app.services.auth.auth_service import require_authorized_user
from app.schemas.PaginationResponse import PaginatedResponse

logger = logging.getLogger(__name__)

router_asset_confirmation = APIRouter(prefix="/asset-confirmations", tags=["Asset Confirmations"])

@router_asset_confirmation.post(
    "/request",
    status_code=status.HTTP_201_CREATED,
    summary="Создать заявку на подтверждение наличия актива"
)
async def endpoint_create_confirmation_request(
        request: CreateConfirmationRequest,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Создает заявку на подтверждение.
    - Если указан employee_id: создает запросы на все активы, числящиеся за этим сотрудником.
    - Если указан asset_id или material_id: создает запрос для всех текущих ответственных за этот актив.
    """
    try:
        result = await create_confirmation_request(
            db=db,
            request=request,
            requested_by=current_user.employee_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при создании заявки на подтверждение: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Внутренняя ошибка сервера")


@router_asset_confirmation.post(
    "/confirm",
    status_code=status.HTTP_200_OK,
    summary="Подтвердить наличие актива (вручную или через QR-код)"
)
async def endpoint_confirm_asset(
        request: ConfirmAssetRequest,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Подтверждает наличие актива.
    Принимает либо прямой asset_id, либо qr_data.
    QR-код должен содержать JSON: {"inventory_id": "...", "serial_number": "..."}
    или просто строку с инвентарным/серийным номером.
    """
    if not request.asset_id and not request.qr_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Необходимо указать либо asset_id, либо qr_data"
        )

    if request.status in ["not_found", "damaged"] and not request.comment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Комментарий обязателен при статусе 'not_found' или 'damaged'"
        )

    try:
        result = await process_confirmation(
            db=db,
            request=request,
            current_user_employee_id=current_user.employee_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при подтверждении актива: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Внутренняя ошибка сервера")


@router_asset_confirmation.get(
    "/",
    response_model=PaginatedResponse,
    summary="Получить список запросов на подтверждение"
)
async def endpoint_get_confirmations_list(
        asset_id: Optional[int] = Query(None, description="Фильтр по ID актива"),
        status_confirmation: Optional[Literal["pending", "confirmed", "not_found", "damaged"]] = Query(None, description="Фильтр по статусу"),
        only_my: Optional[bool] = Query(False, description="Показать только мои подтверждения"),
        employee_id: Optional[str] = Query(None, description="Фильтр по табельному номеру сотрудника"),
        page: int = Query(1, ge=1, description="Номер страницы (начинается с 1)"),
        page_size: int = Query(50, ge=1, le=200, description="Размер страницы"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Возвращает список запросов на подтверждение с возможностью фильтрации и пагинацией.
    Данные обогащены названиями активов и ФИО сотрудников.
    """
    if only_my:
        employee_id = current_user.employee_id

    try:
        result = await get_confirmations_list(
            db=db,
            asset_id=asset_id,
            employee_id=employee_id,
            status=status_confirmation,
            page=page,
            page_size=page_size
        )
        return PaginatedResponse(**result)
    except Exception as e:
        logger.error(f"Ошибка при получении списка подтверждений: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Внутренняя ошибка сервера")

# ==============================================================================
# НОВЫЙ ЭНДПОИНТ: Получение последней записи о подтверждении актива
# ==============================================================================
@router_asset_confirmation.get(
    "/last",
    response_model=Optional[AssetConfirmationResponse],
    summary="Получить последнюю запись о подтверждении наличия актива"
)
async def endpoint_get_last_confirmation(
        asset_id: int = Query(..., description="ID актива"),
        employee_id: Optional[str] = Query(
            None,
            description="Табельный номер сотрудника. Если не указан — вернется последнее подтверждение любого сотрудника"
        ),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Возвращает последнюю запись о подтверждении наличия актива.

    Полезные сценарии использования:
    - UI показывает на карточке актива статус последнего подтверждения (когда и кем).
    - Если указан employee_id — можно узнать, когда конкретный сотрудник последний раз
      подтверждал наличие актива.
    - Если записей нет — вернется null.
    """
    try:
        result = await get_last_confirmation(
            db=db,
            asset_id=asset_id,
            employee_id=employee_id
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка при получении последней записи о подтверждении: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Внутренняя ошибка сервера")