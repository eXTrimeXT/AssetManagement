import logging
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from app.schemas.assets.AssetCreate import AssetCreate
from app.schemas.assets.AssetUpdate import AssetUpdate
from app.schemas.assets.AssetResponse import AssetResponse, AssetShortResponse
from app.database.connection import get_db
from app.database.crud_assets import (
    create_asset, get_assets_list, get_asset_by_id, update_asset,
    deactivate_asset, activate_asset, hard_delete_asset,
    get_all_asset_children_recursive, check_duplicate_inventory_id,
    check_duplicate_serial_number, check_parent_exists, get_asset_with_deleted
)
from app.service.auth.auth_service import require_authorized_user
from app.service.permissions.permissions_rules import FilteredByAccessWithParams, has_write_permission, has_read_permission
from app.database.crud_catalog import get_asset_model_by_id

logger = logging.getLogger(__name__)

router_assets = APIRouter(prefix="/assets", tags=["Assets"], dependencies=[Depends(require_authorized_user)])

@router_assets.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset_endpoint(
        asset_in: AssetCreate,
        current_user = Depends(require_authorized_user),
        db: AsyncSession = Depends(get_db)
):
    # 1. Получаем модель с загруженными связями
    model = await get_asset_model_by_id(db, asset_in.model_id)
    if not model:
        logger.warning("Модель актива не найдена")
        raise HTTPException(status_code=400, detail="Модель актива не найдена")

    # 2. Извлекаем en_name типа актива через цепочку: model -> class -> type
    asset_type_en_name = None
    if model.asset_class and model.asset_class.asset_type:
        asset_type_en_name = model.asset_class.asset_type.en_name

    # 3. Проверка write на тип актива (используем en_name, а не ID!)
    if asset_type_en_name and not has_write_permission(current_user, asset_type_en_name):
        logger.error(f"Нет доступа на запись к типу '{asset_type_en_name}'")
        raise HTTPException(403, f"Нет доступа на запись к типу '{asset_type_en_name}'")

    # 4. Остальные проверки
    if await check_duplicate_inventory_id(db, asset_in.inventory_id):
        logger.warning(f"Инвентарный номер уже существует")
        raise HTTPException(status_code=400, detail="Инвентарный номер уже существует")
    if await check_duplicate_serial_number(db, asset_in.serial_number):
        logger.warning(f"Серийный номер уже существует")
        raise HTTPException(status_code=400, detail="Серийный номер уже существует")
    if asset_in.parent_id and not await check_parent_exists(db, asset_in.parent_id):
        logger.warning(f"Родительский актив не найден")
        raise HTTPException(status_code=400, detail="Родительский актив не найден")

    # 5. Создаём актив
    return await create_asset(db, asset_in, current_user_id=current_user.user_id)


@router_assets.get("/", response_model=List[AssetShortResponse])
async def get_assets_endpoint(
        items = Depends(FilteredByAccessWithParams(
            get_assets_list,
            "model.asset_class.asset_type.en_name",
            "read"
        ))
):
    return items


@router_assets.get("/{asset_id}", response_model=AssetResponse)
async def get_asset_endpoint(asset_id: int, db: AsyncSession = Depends(get_db), current_user = Depends(require_authorized_user)):
    asset = await get_asset_by_id(db, asset_id)

    if not asset:
        logger.warning(f"Актив не найден")
        raise HTTPException(status_code=404, detail="Актив не найден")

    if not has_read_permission(current_user, asset.model.asset_class.asset_type.en_name):
        logger.warning(f"Нет доступа для чтения")
        raise HTTPException(status_code=404, detail="Нет доступа для чтения")
    return asset


@router_assets.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset_endpoint(
        asset_id: int,
        asset_data: AssetUpdate,
        current_user=Depends(require_authorized_user),
        db: AsyncSession = Depends(get_db)
):
    asset = await get_asset_by_id(db, asset_id)
    if not asset:
        logger.warning(f"Актив не найден")
        raise HTTPException(status_code=404, detail="Актив не найден")

    if not has_write_permission(current_user, asset.model.asset_class.asset_type.en_name):
        logger.warning(f"Нет доступа для записи")
        raise HTTPException(403, "Нет доступа для записи")

    updated_asset = await update_asset(db, asset_id, asset_data, current_user.user_id)
    if not updated_asset:
        logger.error(f"Ошибка при обновлении")
        raise HTTPException(status_code=404, detail="Ошибка при обновлении")
    return updated_asset


@router_assets.post("/{asset_id}/deactivate", response_model=AssetResponse)
async def deactivate_asset_endpoint(
        asset_id: int,
        current_user = Depends(require_authorized_user),
        db: AsyncSession = Depends(get_db)
):
    asset = await get_asset_by_id(db, asset_id)
    if not asset:
        logger.warning(f"Актив не найден")
        raise HTTPException(404, detail="Актив не найден")
    if not has_write_permission(current_user, asset.model.asset_class.asset_type.en_name):
        logger.warning(f"Нет доступа для записи")
        raise HTTPException(403, "Нет доступа для записи")
    return await deactivate_asset(db, asset_id, current_user.user_id)


@router_assets.post("/{asset_id}/activate", response_model=AssetResponse)
async def activate_asset_endpoint(
        asset_id: int,
        current_user = Depends(require_authorized_user),
        db: AsyncSession = Depends(get_db)
):
    activated = await activate_asset(db, asset_id, current_user.user_id)
    if not activated:
        logger.warning(f"Актив не найден")
        raise HTTPException(status_code=404, detail="Актив не найден")
    return activated


@router_assets.delete("/{asset_id}/hard", status_code=status.HTTP_204_NO_CONTENT)
async def hard_delete_asset_endpoint(
        asset_id: int,
        current_user = Depends(require_authorized_user),
        db: AsyncSession = Depends(get_db)
):
    asset = await get_asset_with_deleted(db, asset_id)

    if not asset:
        logger.warning(f"Актив не найден")
        raise HTTPException(status_code=404, detail="Актив не найден")

    if asset.deleted_at is None:
        logger.warning(f"Сначала деактивируйте актив.")
        raise HTTPException(status_code=400, detail="Сначала деактивируйте актив.")

    if not has_write_permission(current_user, asset.model.asset_class.asset_type.en_name):
        logger.warning(f"Нет доступа для записи")
        raise HTTPException(403, "Нет доступа для записи")

    success = await hard_delete_asset(db, asset_id, current_user.user_id)
    if not success:
        logger.error(f"Ошибка при удалении актива")
        raise HTTPException(status_code=500, detail="Ошибка при удалении актива")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router_assets.get("/{asset_id}/children", response_model=List[AssetShortResponse])
async def get_all_asset_children_endpoint(
        asset_id: int,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user),
        max_depth: Optional[int] = Query(None, ge=1, le=10)
):
    """
    Получить всех дочерних активов рекурсивно.
    Возвращает только те, на которые у пользователя есть право `read`.
    """
    parent = await get_asset_with_deleted(db, asset_id)
    if not parent:
        logger.warning(f"Родительский актив не найден")
        raise HTTPException(status_code=404, detail="Родительский актив не найден")

    if not has_read_permission(current_user, parent.model.asset_class.asset_type.en_name):
        logger.warning(f"Нет доступа для чтения")
        raise HTTPException(status_code=403, detail="Нет доступа для чтения")

    # Получаем детей с загруженными связями
    children = await get_all_asset_children_recursive(db, asset_id, max_depth)

    # === ФИЛЬТРАЦИЯ ПО ПРАВАМ ===
    filtered_children = [
        child for child in children
        if (
                child.model
                and child.model.asset_class
                and child.model.asset_class.asset_type
                and has_read_permission(current_user, child.model.asset_class.asset_type.en_name)
        )
    ]

    # Конвертируем в ответ (Pydantic v2)
    return [AssetShortResponse.model_validate(child) for child in filtered_children]