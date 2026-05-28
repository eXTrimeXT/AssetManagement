import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.database.connection import get_db
from app.schemas.catalog.ClassSchemas import AssetClassCreate, AssetClassUpdate, AssetClassResponse
from app.database.crud_catalog import create_asset_class, get_asset_classes, update_asset_class, delete_asset_class, get_asset_class_by_id
from app.service.auth.auth_service import require_authorized_user
from app.database.crud_asset_types import get_asset_type_by_id
from app.service.permissions.permissions_rules import FilteredByAccessWithParams, has_read_permission, has_write_permission

logger = logging.getLogger(__name__)

router_catalog_classes = APIRouter(prefix="/catalog", tags=["Asset Catalog Classes"], dependencies=[Depends(require_authorized_user)])

def _get_type_en_name_from_id(db, type_id):
    """Вспомогательная функция для получения en_name по ID типа"""
    if not type_id: return None
    t = db.get_sync() if hasattr(db, 'get_sync') else None # fallback
    # Для async сессии используем отдельный вызов в роутере или передаём en_name
    return None

@router_catalog_classes.post("/classes", response_model=AssetClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(data: AssetClassCreate, db: AsyncSession = Depends(get_db), current_user = Depends(require_authorized_user)):
    # Проверяем write на тип, к которому привязываем класс
    type_obj = await get_asset_type_by_id(db, data.class_type_id)
    if type_obj and not has_write_permission(current_user, type_obj.en_name):
        logger.warning(f"Нет доступа на запись к типу '{type_obj.en_name}'")
        raise HTTPException(403, f"Нет доступа на запись к типу '{type_obj.en_name}'")
    return await create_asset_class(db, data)

@router_catalog_classes.get("/classes", response_model=List[AssetClassResponse])
async def list_classes(items = Depends(FilteredByAccessWithParams(get_asset_classes, "asset_type.en_name", "read"))):
    return items

@router_catalog_classes.get("/classes/{class_id}", response_model=AssetClassResponse)
async def get_class(class_id: int, db: AsyncSession = Depends(get_db), current_user = Depends(require_authorized_user)):
    obj = await get_asset_class_by_id(db, class_id)
    if not obj:
        logger.warning(f"Класс не найден")
        raise HTTPException(404, "Класс не найден")
    if not has_read_permission(current_user, obj.asset_type.en_name):
        logger.warning("Нет доступа для чтения")
        raise HTTPException(404, "Нет доступа для чтения")
    return obj

@router_catalog_classes.patch("/classes/{class_id}", response_model=AssetClassResponse)
async def patch_class(class_id: int, data: AssetClassUpdate, db: AsyncSession = Depends(get_db), current_user = Depends(require_authorized_user)):
    obj = await get_asset_class_by_id(db, class_id)
    if not obj:
        logger.warning(f"Класс не найден")
        raise HTTPException(404, "Класс не найден")
    # Если меняется тип, проверяем write на новый тип
    target_type_id = data.class_type_id if data.class_type_id else obj.class_type_id
    if target_type_id:
        new_type = await get_asset_type_by_id(db, target_type_id)
        if new_type and not has_write_permission(current_user, new_type.en_name):
            logger.warning(f"Нет доступа на запись к типу '{new_type.en_name}'")
            raise HTTPException(403, f"Нет доступа на запись к типу '{new_type.en_name}'")
    return await update_asset_class(db, class_id, data)

@router_catalog_classes.delete("/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(class_id: int, db: AsyncSession = Depends(get_db), current_user = Depends(require_authorized_user)):
    obj = await get_asset_class_by_id(db, class_id)
    if not obj:
        logger.warning(f"Класс не найден")
        raise HTTPException(404, "Класс не найден")
    if not has_write_permission(current_user, obj.asset_type.en_name):
        logger.warning(f"Нет доступа для записи")
        raise HTTPException(403, "Нет доступа для записи")
    await delete_asset_class(db, class_id)