import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database.connection import get_db
from app.database.assets.crud_asset_model import (
    create_asset_model, get_asset_model_by_id, get_asset_models_list,
    update_asset_model, delete_asset_model
)
from app.schemas.assets.AssetModelSchemas import AssetModelCreate, AssetModelUpdate, AssetModelResponse
from app.services.auth.auth_service import require_authorized_user, get_token_from_request, get_user_from_token, check_assets_is_admin
from app.services.auth.permission_checker import check_permission
from app.database.assets import get_asset_type_by_id

logger = logging.getLogger(__name__)
router_asset_models = APIRouter(prefix="/asset-models", tags=["Asset Models"])


@router_asset_models.post(
    "/",
    response_model=AssetModelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать модель актива / Create Asset Model",
    description=(
            "RU: Создает новую модель актива. Проверяет наличие права на запись (`write`) "
            "для типа актива, связанного с указанной моделью (через `asset_type_id`). "
            "Если тип актива не найден — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Creates a new asset model. Checks for write permission (`write`) "
            "on the asset type associated with the model (via `asset_type_id`). "
            "If the asset type is not found, a 404 error is returned. "
            "User authorization is required."
    )
)
async def create_asset_model_endpoint(
        data: AssetModelCreate,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Создать модель актива.
    Проверяем право write на тип актива (через class_id -> asset_type).
    """
    # Получаем класс для определения типа
    asset_type = await get_asset_type_by_id(db, data.asset_type_id)
    if not asset_type:
        raise HTTPException(status_code=404, detail="Класс актива не найден")

    # Проверяем право write на тип
    has_perm = await check_permission(request, asset_type.en_name, "write")
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'write' на тип актива '{asset_type.en_name}'"
        )

    return await create_asset_model(db, data, current_user.employee_id)

@router_asset_models.get(
    "/",
    response_model=List[AssetModelResponse],
    summary="Получить список моделей активов / Get Asset Models List",
    description=(
            "RU: Возвращает список моделей активов с поддержкой пагинации (`skip`, `limit`). "
            "Для администраторов активов (`check_assets_is_admin`) возвращаются все модели. "
            "Для остальных пользователей список фильтруется на основе права `read` "
            "на соответствующий тип актива (`asset_type.en_name`). "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns a list of asset models with pagination support (`skip`, `limit`). "
            "For asset administrators (`check_assets_is_admin`), all models are returned. "
            "For other users, the list is filtered based on the `read` permission "
            "for the corresponding asset type (`asset_type.en_name`). "
            "User authorization is required."
    )
)
async def get_asset_models(
        request: Request,
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        # model_name: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить список моделей активов."""
    all_models = await get_asset_models_list(db, skip, limit)

    # Исключение для админов активов: доступ ко всем типам
    token = await get_token_from_request(request)
    if check_assets_is_admin(token):
        return all_models

    user_data = get_user_from_token(token)
    permissions = user_data.permissions

    accessible_models = []
    for asset_model in all_models:
        if asset_model.asset_type:
            en_name = asset_model.asset_type.en_name
            resource_perms = permissions.get(en_name, {})
            if resource_perms.get("read", False):
                accessible_models.append(asset_model)

    return accessible_models

@router_asset_models.get(
    "/{model_id}",
    response_model=AssetModelResponse,
    summary="Получить модель актива по ID / Get Asset Model by ID",
    description=(
            "RU: Возвращает подробную информацию о модели актива по её `model_id`. "
            "Проверяет наличие права на чтение (`read`) для типа актива, к которому относится модель. "
            "Если модель не найдена — возвращается ошибка 404, при отсутствии прав — 403. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns detailed information about an asset model by its `model_id`. "
            "Checks for read permission (`read`) on the asset type to which the model belongs. "
            "If the model is not found, a 404 error is returned; if permissions are missing, a 403 error is returned. "
            "User authorization is required."
    )
)
async def get_asset_model(
        model_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    obj = await get_asset_model_by_id(db, model_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Модель актива не найдена")

    # Проверяем право read на тип актива
    if obj.asset_type:
        has_perm = await check_permission(request, obj.asset_type.en_name, "read")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'read' на тип актива '{obj.asset_type.en_name}'"
            )
    return obj

@router_asset_models.patch(
    "/{model_id}",
    response_model=AssetModelResponse,
    summary="Обновить модель актива / Update Asset Model",
    description=(
            "RU: Обновляет данные существующей модели актива по её `model_id`. "
            "Проверяет наличие права на запись (`write`) для типа актива — "
            "используется новый `asset_type_id` из запроса, если он указан, иначе — текущий. "
            "Если модель не найдена — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Updates the data of an existing asset model by its `model_id`. "
            "Checks for write permission (`write`) on the asset type — "
            "uses the new `asset_type_id` from the request if provided, otherwise the current one. "
            "If the model is not found, a 404 error is returned. "
            "User authorization is required."
    )
)
async def update_asset_model_endpoint(
        model_id: int,
        data: AssetModelUpdate,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    obj = await get_asset_model_by_id(db, model_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Модель актива не найдена")

    # Определяем класс для проверки (новый или старый)
    asset_type_id = data.asset_type_id if data.asset_type_id else obj.asset_type_id
    asset_type = await get_asset_type_by_id(db, asset_type_id)

    if asset_type:
        has_perm = await check_permission(request, asset_type.en_name, "write")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'write' на тип актива '{asset_type.en_name}'"
            )

    updated = await update_asset_model(db, model_id, data, current_user.employee_id)
    return updated

@router_asset_models.delete(
    "/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить модель актива / Delete Asset Model",
    description=(
            "RU: Удаляет модель актива по её `model_id`. "
            "Перед удалением проверяется наличие права на запись (`write`) для типа актива, "
            "к которому относится модель. Если модель не найдена — возвращается ошибка 404. "
            "При успешном удалении возвращается статус 204 (No Content). "
            "Требуется авторизация пользователя.\n\n"
            "EN: Deletes an asset model by its `model_id`. "
            "Before deletion, write permission (`write`) is checked for the asset type "
            "to which the model belongs. If the model is not found, a 404 error is returned. "
            "On successful deletion, a 204 (No Content) status is returned. "
            "User authorization is required."
    )
)
async def delete_asset_model_endpoint(
        model_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    obj = await get_asset_model_by_id(db, model_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Модель актива не найдена")

    if obj.asset_type:
        has_perm = await check_permission(request, obj.asset_type.en_name, "write")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'write' на тип актива '{obj.asset_type.en_name}'"
            )

    success = await delete_asset_model(db, model_id)
    if not success:
        raise HTTPException(status_code=404, detail="Модель актива не найдена")