import logging
import math

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database.connection import get_db
from app.database.assets.asset import (
    create_asset, get_asset_by_id, get_assets_list,
    update_asset, delete_asset, get_asset_children
)
from app.schemas.assets.asset import AssetCreate, AssetUpdate, AssetResponse, AssetShortResponse
from app.services.auth.auth_service import (
    require_authorized_user,
    get_token_from_request,
    get_user_from_token,
)
from app.services.auth.permission_checker import check_permission, check_asset_permission
from app.schemas.PaginationResponse import PaginatedResponse

logger = logging.getLogger(__name__)
router_assets = APIRouter(prefix="/assets", tags=["Assets"])


@router_assets.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset_endpoint(
        request: Request,
        data: AssetCreate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Создать актив. Проверка права write на тип актива."""
    await check_asset_permission(db, request, data.asset_type_id, "write")
    return await create_asset(db, data, current_user.employee_id)


@router_assets.get(
    "/",
    response_model=PaginatedResponse[AssetResponse],
    summary="Получить список активов (с пагинацией)"
)
async def get_assets(
        request: Request,
        page: int = Query(1, ge=1, description="Номер страницы (начинается с 1)"),
        page_size: int = Query(50, ge=1, le=100, description="Размер страницы"),
        name: Optional[str] = Query(None),
        inventory_id: Optional[str] = Query(None),
        serial_number: Optional[str] = Query(None),
        asset_status: Optional[str] = Query(None),
        model_id: Optional[int] = Query(None),
        asset_type_id: Optional[int] = Query(None),
        parent_id: Optional[int] = Query(None),
        location_id: Optional[int] = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить страницу активов с фильтрацией по правам."""
    token = await get_token_from_request(request)
    user_data = get_user_from_token(token)
    permissions = user_data.permissions

    allowed_type_en_names: List[str] = [
        en_name for en_name, perms in permissions.items()
        if perms.get("read", False)
    ]

    assets, total = await get_assets_list(
        db=db,
        page=page,
        page_size=page_size,
        name=name,
        inventory_id=inventory_id,
        serial_number=serial_number,
        asset_status=asset_status,
        model_id=model_id,
        asset_type_id=asset_type_id,
        parent_id=parent_id,
        location_id=location_id,
        allowed_type_en_names=allowed_type_en_names,
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse(
        items=list(assets),
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )

@router_assets.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
        request: Request,
        asset_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    obj = await get_asset_by_id(db, asset_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Актив не найден")

    # Проверка прав напрямую через asset_type_id
    await check_asset_permission(db, request, obj.asset_type_id, "read")
    return obj

@router_assets.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset_endpoint(
        request: Request,
        asset_id: int,
        data: AssetUpdate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    obj = await get_asset_by_id(db, asset_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Актив не найден")

    # Итоговый asset_type_id после обновления
    final_asset_type_id = data.asset_type_id if data.asset_type_id is not None else obj.asset_type_id
    await check_asset_permission(db, request, final_asset_type_id, "write")
    updated = await update_asset(db, asset_id, data, current_user.employee_id)
    return updated

@router_assets.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset_endpoint(
        request: Request,
        asset_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    obj = await get_asset_by_id(db, asset_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Актив не найден")

    # Проверка прав напрямую через asset_type_id
    await check_asset_permission(db, request, obj.asset_type_id, "write")

    success = await delete_asset(db, asset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Актив не найден")

@router_assets.get("/{asset_id}/children", response_model=List[AssetShortResponse])
async def get_asset_children_endpoint(
        request: Request,
        asset_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получение всех детей актива через parent_id"""
    parent = await get_asset_by_id(db, asset_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Актив не найден")

    # Проверка прав напрямую через asset_type_id родителя
    await check_asset_permission(db, request, parent.asset_type_id, "read")

    children = await get_asset_children(db, asset_id)
    return children