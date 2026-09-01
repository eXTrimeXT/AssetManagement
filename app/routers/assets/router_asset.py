import logging
import math

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database.connection import get_db
from app.database.assets.crud_asset import (
    create_asset, get_asset_by_id, get_assets_list,
    update_asset, delete_asset, get_asset_children, bulk_enrich_assets
)
from app.schemas.assets.AssetSchemas import AssetCreate, AssetUpdate, AssetResponse, AssetShortResponse
from app.services.auth.auth_service import (
    require_authorized_user,
    get_token_from_request,
    get_user_from_token, check_assets_is_admin,
)
from app.services.auth.permission_checker import check_permission, check_asset_permission
from app.schemas.PaginationResponse import PaginatedResponse
from app.database.zup import get_position_by_guid
from app.database.zup.crud_zup_departments import get_hierarchy_departments
from app.schemas.assets.AssetAssignmentSchemas import AssetUserFullResponse

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


async def enrich_users_data(db: AsyncSession, users_data: list) -> list:
    """Дополняет данные о пользователях иерархией и должностью"""
    enriched = []
    for user in users_data:
        user_dict = user.model_dump() if hasattr(user, 'model_dump') else user

        # Получаем иерархию подразделений
        if user_dict.get("department_guid"):
            hierarchy = await get_hierarchy_departments(db, user_dict["department_guid"])
            if hierarchy:
                user_dict["society"] = hierarchy.society
                user_dict["department"] = hierarchy.department
                user_dict["division"] = hierarchy.division
                user_dict["group"] = hierarchy.group

        # Получаем должность
        if user_dict.get("position_guid"):
            position = await get_position_by_guid(db, user_dict["position_guid"])
            if position:
                from app.schemas.zup.PositionSchemas import PositionResponse
                user_dict["position"] = PositionResponse.model_validate(position)

        enriched.append(AssetUserFullResponse(**user_dict))

    return enriched

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
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить страницу активов с фильтрацией по правам."""
    token = await get_token_from_request(request)

    if check_assets_is_admin(token):
        allowed_type_en_names = None
    else:
        user_data = get_user_from_token(token)
        permissions = user_data.permissions
        allowed_type_en_names = [
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
        allowed_type_en_names=allowed_type_en_names,
    )

    # === Дополняем данные о пользователях ===
    # for asset in assets:
    #     if asset.users:
    #         asset.users = await enrich_users_data(db, asset.users)
    #     if asset.responsible_users:
    #         asset.responsible_users = await enrich_users_data(db, asset.responsible_users)
    # === Дополняем данные о пользователях (Bulk Fetch) ===
    await bulk_enrich_assets(db, list(assets))

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