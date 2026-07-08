# import logging
# import math
#
# from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
# from sqlalchemy.ext.asyncio import AsyncSession
# from typing import List, Optional
# from app.database.connection import get_db
# from app.database.assets.asset import (
#     create_asset, get_asset_by_id, get_assets_list,
#     update_asset, delete_asset, get_asset_children
# )
# from app.database.assets.asset_model import get_asset_model_by_id
# from app.database.assets.asset_assignment import get_active_assignments_for_asset
# from app.schemas.assets.asset import AssetCreate, AssetUpdate, AssetResponse, AssetShortResponse
# from app.services.auth.auth_service import (
#     require_authorized_user,
#     get_token_from_request,
#     get_user_from_token,
#     # get_user_permissions_from_redis
# )
# from app.services.auth.permission_checker import check_permission
# from app.schemas.PaginationResponse import PaginatedResponse
#
# logger = logging.getLogger(__name__)
# router_assets = APIRouter(prefix="/assets", tags=["Assets"])
#
#
# @router_assets.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
# async def create_asset_endpoint(
#         data: AssetCreate,
#         request: Request,
#         db: AsyncSession = Depends(get_db),
#         current_user=Depends(require_authorized_user)
# ):
#     """
#     Создать актив.
#     Проверяем право write на тип актива (через model_id → class → type).
#     """
#     # Если есть model_id, проверяем право на тип актива
#     if data.model_id:
#         asset_model = await get_asset_model_by_id(db, data.model_id)
#         if not asset_model:
#             raise HTTPException(status_code=404, detail="Модель актива не найдена")
#
#         if asset_model.asset_class and asset_model.asset_class.asset_type:
#             en_name = asset_model.asset_class.asset_type.en_name
#             has_perm = await check_permission(request, en_name, "write")
#             if not has_perm:
#                 raise HTTPException(
#                     status_code=403,
#                     detail=f"Нет права 'write' на тип актива '{en_name}'"
#                 )
#
#     return await create_asset(db, data, current_user.employee_id)
#
# @router_assets.get(
#     "/",
#     response_model=PaginatedResponse[AssetResponse],
#     summary="Получить список активов (с пагинацией)"
# )
# async def get_assets(
#         page: int = Query(1, ge=1, description="Номер страницы (начинается с 1)"),
#         page_size: int = Query(50, ge=1, le=100, description="Размер страницы"),
#         name: Optional[str] = Query(None),
#         inventory_id: Optional[str] = Query(None),
#         serial_number: Optional[str] = Query(None),
#         asset_status: Optional[str] = Query(None),
#         model_id: Optional[int] = Query(None),
#         asset_type_id: Optional[int] = Query(None),
#         parent_id: Optional[int] = Query(None),
#         location_id: Optional[int] = Query(None),
#         request: Request = None,
#         db: AsyncSession = Depends(get_db),
#         current_user=Depends(require_authorized_user)
# ):
#     """
#     Получить страницу активов.
#     Фильтруем по правам пользователя (только те типы, на которые есть read).
#     """
#     # Получаем права пользователя из Redis один раз
#     token = await get_token_from_request(request)
#     user_data = get_user_from_token(token)
#     # permissions = await get_user_permissions_from_redis(user_data.login) or {}
#     permissions = user_data.permissions
#
#     # Собираем список разрешённых типов активов (en_name), на которые есть read
#     allowed_type_en_names: List[str] = [
#         en_name for en_name, perms in permissions.items()
#         if perms.get("read", False)
#     ]
#
#     assets, total = await get_assets_list(
#         db=db,
#         page=page,
#         page_size=page_size,
#         name=name,
#         inventory_id=inventory_id,
#         serial_number=serial_number,
#         asset_status=asset_status,
#         model_id=model_id,
#         asset_type_id=asset_type_id,
#         parent_id=parent_id,
#         location_id=location_id,
#         # allowed_type_en_names=allowed_type_en_names,
#     )
#
#     # Подгружаем current_users для каждого актива
#     for asset in assets:
#         active_users = await get_active_assignments_for_asset(db, asset.asset_id)
#         asset.current_users = active_users
#
#     total_pages = math.ceil(total / page_size) if total > 0 else 0
#
#     return PaginatedResponse(
#         items=list(assets),
#         total=total,
#         page=page,
#         page_size=page_size,
#         total_pages=total_pages,
#         has_next=page < total_pages,
#         has_previous=page > 1,
#     )
#
# @router_assets.get("/{asset_id}", response_model=AssetResponse)
# async def get_asset(
#         asset_id: int,
#         request: Request,
#         db: AsyncSession = Depends(get_db),
#         current_user=Depends(require_authorized_user)
# ):
#     obj = await get_asset_by_id(db, asset_id)
#     if not obj:
#         raise HTTPException(status_code=404, detail="Актив не найден")
#
#     # Проверяем право read на тип актива
#     if obj.model and obj.model.asset_class and obj.model.asset_class.asset_type:
#         en_name = obj.model.asset_class.asset_type.en_name
#         has_perm = await check_permission(request, en_name, "read")
#         if not has_perm:
#             raise HTTPException(
#                 status_code=403,
#                 detail=f"Нет права 'read' на тип актива '{en_name}'"
#             )
#     return obj
#
#
# @router_assets.patch("/{asset_id}", response_model=AssetResponse)
# async def update_asset_endpoint(
#         asset_id: int,
#         data: AssetUpdate,
#         request: Request,
#         db: AsyncSession = Depends(get_db),
#         current_user=Depends(require_authorized_user)
# ):
#     obj = await get_asset_by_id(db, asset_id)
#     if not obj:
#         raise HTTPException(status_code=404, detail="Актив не найден")
#
#     # Проверяем право write на тип актива
#     if obj.model and obj.model.asset_class and obj.model.asset_class.asset_type:
#         en_name = obj.model.asset_class.asset_type.en_name
#         has_perm = await check_permission(request, en_name, "write")
#         if not has_perm:
#             raise HTTPException(
#                 status_code=403,
#                 detail=f"Нет права 'write' на тип актива '{en_name}'"
#             )
#
#     updated = await update_asset(db, asset_id, data, current_user.employee_id)
#     return updated
#
#
# @router_assets.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
# async def delete_asset_endpoint(
#         asset_id: int,
#         request: Request,
#         db: AsyncSession = Depends(get_db),
#         current_user=Depends(require_authorized_user)
# ):
#     obj = await get_asset_by_id(db, asset_id)
#     if not obj:
#         raise HTTPException(status_code=404, detail="Актив не найден")
#
#     # Проверяем право write на тип актива
#     if obj.model and obj.model.asset_class and obj.model.asset_class.asset_type:
#         en_name = obj.model.asset_class.asset_type.en_name
#         has_perm = await check_permission(request, en_name, "write")
#         if not has_perm:
#             raise HTTPException(
#                 status_code=403,
#                 detail=f"Нет права 'write' на тип актива '{en_name}'"
#             )
#
#     success = await delete_asset(db, asset_id)
#     if not success:
#         raise HTTPException(status_code=404, detail="Актив не найден")
#
#
# @router_assets.get("/{asset_id}/children", response_model=List[AssetShortResponse])
# async def get_asset_children_endpoint(
#         asset_id: int,
#         request: Request,
#         db: AsyncSession = Depends(get_db),
#         current_user=Depends(require_authorized_user)
# ):
#     """Получение всех детей актива через parent_id"""
#     parent = await get_asset_by_id(db, asset_id)
#     if not parent:
#         raise HTTPException(status_code=404, detail="Актив не найден")
#
#     # Проверяем право read на тип родителя
#     if parent.model and parent.model.asset_class and parent.model.asset_class.asset_type:
#         en_name = parent.model.asset_class.asset_type.en_name
#         has_perm = await check_permission(request, en_name, "read")
#         if not has_perm:
#             raise HTTPException(
#                 status_code=403,
#                 detail=f"Нет права 'read' на тип актива '{en_name}'"
#             )
#
#     children = await get_asset_children(db, asset_id)
#     return children



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
from app.database.assets.asset_type import get_asset_type_by_id
from app.database.assets.asset_assignment import get_active_assignments_for_asset
from app.schemas.assets.asset import AssetCreate, AssetUpdate, AssetResponse, AssetShortResponse
from app.services.auth.auth_service import (
    require_authorized_user,
    get_token_from_request,
    get_user_from_token,
)
from app.services.auth.permission_checker import check_permission
from app.schemas.PaginationResponse import PaginatedResponse

logger = logging.getLogger(__name__)
router_assets = APIRouter(prefix="/assets", tags=["Assets"])


@router_assets.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset_endpoint(
        data: AssetCreate,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Создать актив.
    Проверяем право write на тип актива (напрямую через asset_type_id).
    """
    # Проверяем право на тип актива напрямую через asset_type_id
    if data.asset_type_id:
        asset_type = await get_asset_type_by_id(db, data.asset_type_id)
        if not asset_type:
            raise HTTPException(status_code=404, detail="Тип актива не найден")

        en_name = asset_type.en_name
        has_perm = await check_permission(request, en_name, "write")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'write' на тип актива '{en_name}'"
            )

    return await create_asset(db, data, current_user.employee_id)


@router_assets.get(
    "/",
    response_model=PaginatedResponse[AssetResponse],
    summary="Получить список активов (с пагинацией)"
)
async def get_assets(
        page: int = Query(1, ge=1, description="Номер страницы (начинается с 1)"),
        page_size: int = Query(50, ge=1, le=100, description="Размер страницы"),
        name: Optional[str] = Query(None),
        inventory_id: Optional[str] = Query(None),
        serial_number: Optional[str] = Query(None),
        asset_status: Optional[str] = Query(None),
        model_id: Optional[int] = Query(None),
        class_id: Optional[int] = Query(None),
        asset_type_id: Optional[int] = Query(None),
        parent_id: Optional[int] = Query(None),
        location_id: Optional[int] = Query(None),
        request: Request = None,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Получить страницу активов.
    Фильтруем по правам пользователя (только те типы, на которые есть read).
    """
    token = await get_token_from_request(request)
    user_data = get_user_from_token(token)
    permissions = user_data.permissions

    # Собираем список разрешённых типов активов (en_name), на которые есть read
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
        class_id=class_id,
        asset_type_id=asset_type_id,
        parent_id=parent_id,
        location_id=location_id,
        allowed_type_en_names=allowed_type_en_names,   # Возвращаем фильтрацию по правам
    )

    # Подгружаем current_users для каждого актива
    for asset in assets:
        active_users = await get_active_assignments_for_asset(db, asset.asset_id)
        asset.current_users = active_users

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
        asset_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    obj = await get_asset_by_id(db, asset_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Актив не найден")

    # Проверяем право read на тип актива напрямую через asset_type
    if obj.asset_type:
        en_name = obj.asset_type.en_name
        has_perm = await check_permission(request, en_name, "read")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'read' на тип актива '{en_name}'"
            )
    return obj


@router_assets.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset_endpoint(
        asset_id: int,
        data: AssetUpdate,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    obj = await get_asset_by_id(db, asset_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Актив не найден")

    # Проверяем право write на тип актива напрямую через asset_type
    if obj.asset_type:
        en_name = obj.asset_type.en_name
        has_perm = await check_permission(request, en_name, "write")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'write' на тип актива '{en_name}'"
            )

    updated = await update_asset(db, asset_id, data, current_user.employee_id)
    return updated


@router_assets.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset_endpoint(
        asset_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    obj = await get_asset_by_id(db, asset_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Актив не найден")

    # Проверяем право write на тип актива напрямую через asset_type
    if obj.asset_type:
        en_name = obj.asset_type.en_name
        has_perm = await check_permission(request, en_name, "write")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'write' на тип актива '{en_name}'"
            )

    success = await delete_asset(db, asset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Актив не найден")


@router_assets.get("/{asset_id}/children", response_model=List[AssetShortResponse])
async def get_asset_children_endpoint(
        asset_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получение всех детей актива через parent_id"""
    parent = await get_asset_by_id(db, asset_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Актив не найден")

    # Проверяем право read на тип родителя напрямую через asset_type
    if parent.asset_type:
        en_name = parent.asset_type.en_name
        has_perm = await check_permission(request, en_name, "read")
        if not has_perm:
            raise HTTPException(
                status_code=403,
                detail=f"Нет права 'read' на тип актива '{en_name}'"
            )

    children = await get_asset_children(db, asset_id)
    return children