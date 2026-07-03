import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database.connection import get_db
from app.database.assets.asset_class import (
    create_asset_class, get_asset_class_by_id, get_asset_classes_list,
    update_asset_class, delete_asset_class
)
from app.database.assets.asset_type import get_asset_type_by_id
from app.schemas.assets.asset_class import AssetClassCreate, AssetClassUpdate, AssetClassResponse
from app.services.auth.auth_service import require_authorized_user, get_token_from_request, get_user_from_token, \
    get_user_permissions_from_redis
from app.services.auth.permission_checker import check_permission

logger = logging.getLogger(__name__)
router_asset_classes = APIRouter(prefix="/asset-classes", tags=["Asset Classes"])


@router_asset_classes.post("/", response_model=AssetClassResponse, status_code=status.HTTP_201_CREATED)
async def create_asset_class_endpoint(
        data: AssetClassCreate,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Создать класс актива.
    Проверяем право write на тип актива (через asset_type_id).
    """
    # Получаем тип актива для определения en_name
    asset_type = await get_asset_type_by_id(db, data.asset_type_id)
    if not asset_type:
        raise HTTPException(status_code=404, detail="Тип актива не найден")

    # Проверяем право write на тип
    has_perm = await check_permission(request, asset_type.en_name, "write")
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'write' на тип актива '{asset_type.en_name}'"
        )

    return await create_asset_class(db, data, current_user.employee_id)


@router_asset_classes.get("/", response_model=List[AssetClassResponse])
async def get_asset_classes(
        request: Request,
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        class_name: Optional[str] = Query(None),
        asset_type_id: Optional[int] = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Получить список классов активов.
    Возвращает только те классы, на тип актива которых у пользователя есть право read.
    """
    # Получаем все классы с учётом фильтров
    all_classes = await get_asset_classes_list(db, skip, limit, class_name, asset_type_id)

    # Получаем права пользователя из Redis один раз (оптимизация)
    token = await get_token_from_request(request)
    user_data = get_user_from_token(token)
    permissions = await get_user_permissions_from_redis(user_data.login) or {}

    # Фильтруем по правам read на тип актива
    accessible_classes = []
    for asset_class in all_classes:
        # Получаем en_name типа актива
        if asset_class.asset_type:
            en_name = asset_class.asset_type.en_name
            # Проверяем право read (локально, без обращений к Redis)
            resource_perms = permissions.get(en_name, {})
            if resource_perms.get("read", False):
                accessible_classes.append(asset_class)

    return accessible_classes


@router_asset_classes.get("/{class_id}", response_model=AssetClassResponse)
async def get_asset_class(
        class_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    obj = await get_asset_class_by_id(db, class_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Класс актива не найден")

    # Проверяем право read на тип актива
    if obj.asset_type:
        has_perm = await check_permission(request, obj.asset_type.en_name, "read")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'read' на тип актива '{obj.asset_type.en_name}'"
            )

    return obj


@router_asset_classes.patch("/{class_id}", response_model=AssetClassResponse)
async def update_asset_class_endpoint(
        class_id: int,
        data: AssetClassUpdate,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    obj = await get_asset_class_by_id(db, class_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Класс актива не найден")

    # Определяем тип для проверки (новый или старый)
    asset_type_id = data.asset_type_id if data.asset_type_id else obj.asset_type_id
    asset_type = await get_asset_type_by_id(db, asset_type_id)

    if asset_type:
        has_perm = await check_permission(request, asset_type.en_name, "write")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'write' на тип актива '{asset_type.en_name}'"
            )

    updated = await update_asset_class(db, class_id, data, current_user.employee_id)
    return updated


@router_asset_classes.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset_class_endpoint(
        class_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    obj = await get_asset_class_by_id(db, class_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Класс актива не найден")

    if obj.asset_type:
        has_perm = await check_permission(request, obj.asset_type.en_name, "write")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'write' на тип актива '{obj.asset_type.en_name}'"
            )

    success = await delete_asset_class(db, class_id)
    if not success:
        raise HTTPException(status_code=404, detail="Класс актива не найден")