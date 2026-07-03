import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database.connection import get_db
from app.database.assets.asset_type import (
    create_asset_type, get_asset_type_by_id, get_asset_types_list,
    update_asset_type, delete_asset_type
)
from app.schemas.assets.asset_type import AssetTypeCreate, AssetTypeUpdate, AssetTypeResponse
from app.services.auth.auth_service import require_authorized_user
from app.services.auth.permission_checker import check_permission

logger = logging.getLogger(__name__)
router_asset_types = APIRouter(prefix="/asset-types", tags=["Asset Types"])


@router_asset_types.post("/", response_model=AssetTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_asset_type_endpoint(
        data: AssetTypeCreate,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Создать тип актива.
    Проверяем право write на конкретный тип (data.en_name).
    """
    # Проверяем право write на тип актива (en_name = ключ в permissions)
    has_perm = await check_permission(request, data.en_name, "write")
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'write' на тип актива '{data.en_name}'"
        )

    return await create_asset_type(db, data, current_user.employee_id)


@router_asset_types.get("/", response_model=List[AssetTypeResponse])
async def get_asset_types(
        request: Request,
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        name: Optional[str] = Query(None),
        en_name: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Получить список типов активов.
    Возвращает только те типы, на которые у пользователя есть право read.
    """
    # Получаем все типы с учётом фильтров
    all_types = await get_asset_types_list(db, skip, limit, name, en_name)

    # Фильтруем по правам read
    accessible_types = []
    for asset_type in all_types:
        # Проверяем право read на конкретный тип (en_name = ключ в permissions)
        has_perm = await check_permission(request, asset_type.en_name, "read")
        if has_perm:
            accessible_types.append(asset_type)

    return accessible_types


@router_asset_types.get("/{asset_type_id}", response_model=AssetTypeResponse)
async def get_asset_type(
        asset_type_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    obj = await get_asset_type_by_id(db, asset_type_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Тип актива не найден")

    # Проверяем право read на конкретный тип
    has_perm = await check_permission(request, obj.en_name, "read")
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'read' на тип актива '{obj.en_name}'"
        )

    return obj


@router_asset_types.patch("/{asset_type_id}", response_model=AssetTypeResponse)
async def update_asset_type_endpoint(
        asset_type_id: int,
        data: AssetTypeUpdate,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Обновить тип актива.
    Проверяем право write на тип (старый или новый en_name).
    """
    # Получаем текущий объект для определения en_name
    obj = await get_asset_type_by_id(db, asset_type_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Тип актива не найден")

    # Определяем en_name для проверки (новый или старый)
    check_en_name = data.en_name if data.en_name else obj.en_name

    has_perm = await check_permission(request, check_en_name, "write")
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'write' на тип актива '{check_en_name}'"
        )

    updated = await update_asset_type(db, asset_type_id, data)
    return updated


@router_asset_types.delete("/{asset_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset_type_endpoint(
        asset_type_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Удалить тип актива.
    Проверяем право write на тип.
    """
    obj = await get_asset_type_by_id(db, asset_type_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Тип актива не найден")

    has_perm = await check_permission(request, obj.en_name, "write")
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'write' на тип актива '{obj.en_name}'"
        )

    success = await delete_asset_type(db, asset_type_id)
    if not success:
        raise HTTPException(status_code=404, detail="Тип актива не найден")