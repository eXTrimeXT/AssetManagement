import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database.connection import get_db
from app.database.crud_catalog import create_asset_model, get_asset_models, update_asset_model, get_asset_model_by_id, search_asset_models_by_name
from app.schemas.catalog.ModelSchemas import AssetModelCreate, AssetModelUpdate, AssetModelResponse
from app.service.auth.auth_service import require_authorized_user
from app.database.crud_catalog import get_asset_class_by_id
from app.service.permissions.permissions_rules import FilteredByAccessWithParams, has_read_permission, has_write_permission

logger = logging.getLogger(__name__)

router_catalog_models = APIRouter(prefix="/catalog/models", tags=["Asset Catalog Models"], dependencies=[Depends(require_authorized_user)])

@router_catalog_models.post("/", response_model=AssetModelResponse, status_code=200)
async def create_model(data: AssetModelCreate, db: AsyncSession = Depends(get_db), current_user = Depends(require_authorized_user)):
    cls_obj = await get_asset_class_by_id(db, data.class_id)
    if cls_obj and not has_write_permission(current_user, cls_obj.asset_type.en_name):
        logger.warning(f"Нет доступа на запись к типу '{cls_obj.asset_type.en_name}'")
        raise HTTPException(403, f"Нет доступа на запись к типу '{cls_obj.asset_type.en_name}'")
    return await create_asset_model(db, data)

@router_catalog_models.get("/", response_model=List[AssetModelResponse])
async def list_models(
        items = Depends(FilteredByAccessWithParams(get_asset_models, "asset_class.asset_type.en_name", "read"))
):
    return items

@router_catalog_models.get("/search", response_model=List[AssetModelResponse])
async def search_models_endpoint(
        model_name: str = Query(..., min_length=1),
        db: AsyncSession = Depends(get_db)
):
    """Поиск моделей по model_name"""
    return await search_asset_models_by_name(db, model_name)

@router_catalog_models.get("/{model_id}", response_model=AssetModelResponse, status_code=200)
async def get_model(model_id: int, db: AsyncSession = Depends(get_db), current_user = Depends(require_authorized_user)):
    obj = await get_asset_model_by_id(db, model_id)
    if not obj:
        logger.warning("Модель не найдена")
        raise HTTPException(404, "Модель не найдена")
    if not has_read_permission(current_user, obj.asset_class.asset_type.en_name):
        logger.warning("Нет доступа для чтения")
        raise HTTPException(404, "Нет доступа для чтения")
    return obj

@router_catalog_models.patch("/{model_id}", response_model=AssetModelResponse, status_code=200)
async def patch_model(model_id: int, data: AssetModelUpdate, db: AsyncSession = Depends(get_db), current_user = Depends(require_authorized_user)):
    obj = await get_asset_model_by_id(db, model_id)
    if not obj:
        logger.warning("Модель не найдена")
        raise HTTPException(404, "Модель не найдена")
    target_cls_id = data.class_id if data.class_id is not None else obj.class_id
    if target_cls_id:
        cls_obj = await get_asset_class_by_id(db, target_cls_id)
        if cls_obj and not has_write_permission(current_user, cls_obj.asset_type.en_name):
            logger.warning(f"Нет доступа на запись к типуe '{cls_obj.asset_type.en_name}'")
            raise HTTPException(403, f"Нет доступа на запись к типуe '{cls_obj.asset_type.en_name}'")
    return await update_asset_model(db, model_id, data)

@router_catalog_models.delete("/{model_id}", status_code=200)
async def delete_model(model_id: int, db: AsyncSession = Depends(get_db), current_user = Depends(require_authorized_user)):
    obj = await get_asset_model_by_id(db, model_id)
    if not obj:
        logger.warning("Модель не найдена")
        raise HTTPException(404, "Модель не найдена")
    if not has_write_permission(current_user, obj.asset_class.asset_type.en_name):
        logger.warning("Нет доступа для записи")
        raise HTTPException(403, "Нет доступа для записи")
    # Вызов delete_asset_model из crud_catalog, если он там есть, или db.delete(obj)
    await db.delete(obj)
    await db.commit()