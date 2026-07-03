import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database.connection import get_db
from app.database.assets.asset_model import (
    create_asset_model, get_asset_model_by_id, get_asset_models_list,
    update_asset_model, delete_asset_model
)
from app.database.assets.asset_class import get_asset_class_by_id
from app.schemas.assets.asset_model import AssetModelCreate, AssetModelUpdate, AssetModelResponse
from app.services.auth.auth_service import require_authorized_user, get_token_from_request, get_user_from_token, get_user_permissions_from_redis
from app.services.auth.permission_checker import check_permission

logger = logging.getLogger(__name__)
router_asset_models = APIRouter(prefix="/asset-models", tags=["Asset Models"])


@router_asset_models.post("/", response_model=AssetModelResponse, status_code=status.HTTP_201_CREATED)
async def create_asset_model_endpoint(
        data: AssetModelCreate,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Создать модель актива.
    Проверяем право write на тип актива (через class_id → asset_type).
    """
    # Получаем класс для определения типа
    asset_class = await get_asset_class_by_id(db, data.class_id)
    if not asset_class:
        raise HTTPException(status_code=404, detail="Класс актива не найден")

    # Получаем тип через класс
    if not asset_class.asset_type:
        raise HTTPException(status_code=400, detail="У класса не указан тип актива")

    # Проверяем право write на тип
    has_perm = await check_permission(request, asset_class.asset_type.en_name, "write")
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'write' на тип актива '{asset_class.asset_type.en_name}'"
        )

    return await create_asset_model(db, data, current_user.employee_id)


@router_asset_models.get("/", response_model=List[AssetModelResponse])
async def get_asset_models(
        request: Request,
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        model_name: Optional[str] = Query(None),
        class_id: Optional[int] = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Получить список моделей активов.
    Возвращает только те модели, на тип актива которых у пользователя есть право read.
    """
    # Получаем все модели с учётом фильтров
    all_models = await get_asset_models_list(db, skip, limit, model_name, class_id)

    # Получаем права пользователя из Redis один раз (оптимизация)
    token = await get_token_from_request(request)
    user_data = get_user_from_token(token)
    permissions = await get_user_permissions_from_redis(user_data.login) or {}

    # Фильтруем по правам read на тип актива
    accessible_models = []
    for asset_model in all_models:
        # Проходим цепочку: model → class → type → en_name
        if asset_model.asset_class and asset_model.asset_class.asset_type:
            en_name = asset_model.asset_class.asset_type.en_name
            # Проверяем право read (локально, без обращений к Redis)
            resource_perms = permissions.get(en_name, {})
            if resource_perms.get("read", False):
                accessible_models.append(asset_model)

    return accessible_models


@router_asset_models.get("/{model_id}", response_model=AssetModelResponse)
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
    if obj.asset_class and obj.asset_class.asset_type:
        has_perm = await check_permission(request, obj.asset_class.asset_type.en_name, "read")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'read' на тип актива '{obj.asset_class.asset_type.en_name}'"
            )

    return obj


@router_asset_models.patch("/{model_id}", response_model=AssetModelResponse)
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
    class_id = data.class_id if data.class_id else obj.class_id
    asset_class = await get_asset_class_by_id(db, class_id)

    if asset_class and asset_class.asset_type:
        has_perm = await check_permission(request, asset_class.asset_type.en_name, "write")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'write' на тип актива '{asset_class.asset_type.en_name}'"
            )

    updated = await update_asset_model(db, model_id, data, current_user.employee_id)
    return updated


@router_asset_models.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset_model_endpoint(
        model_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    obj = await get_asset_model_by_id(db, model_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Модель актива не найдена")

    if obj.asset_class and obj.asset_class.asset_type:
        has_perm = await check_permission(request, obj.asset_class.asset_type.en_name, "write")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'write' на тип актива '{obj.asset_class.asset_type.en_name}'"
            )

    success = await delete_asset_model(db, model_id)
    if not success:
        raise HTTPException(status_code=404, detail="Модель актива не найдена")