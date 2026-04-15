from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import io
import pandas as pd

from app.database.connection import get_db
from app.schemas.catalog.ClassSchemas import AssetClassCreate, AssetClassUpdate, AssetClassResponse
from app.schemas.catalog.ModelSchemas import AssetModelCreate, AssetModelUpdate, AssetModelResponse
from app.schemas.catalog.CatalogSchemas import AssetCatalogCreate, AssetCatalogResponse

from app.database.crud_catalog import (
    create_asset_class, get_asset_classes, update_asset_class, delete_asset_class,
    create_asset_model, get_asset_models, update_asset_model,
    add_to_catalog, get_catalog_list, get_catalog_stats_by_model
)

router_catalog = APIRouter(prefix="/catalog", tags=["Asset Catalog"])

# === Классы оборудования ===
@router_catalog.post("/classes", response_model=AssetClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(data: AssetClassCreate, db: AsyncSession = Depends(get_db)):
    return await create_asset_class(db, data)

@router_catalog.get("/classes", response_model=List[AssetClassResponse])
async def list_classes(skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)):
    return await get_asset_classes(db, skip, limit)

@router_catalog.patch("/classes/{class_id}", response_model=AssetClassResponse)
async def patch_class(class_id: int, data: AssetClassUpdate, db: AsyncSession = Depends(get_db)):
    res = await update_asset_class(db, class_id, data)
    if not res: raise HTTPException(404, "Class not found")
    return res

@router_catalog.delete("/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(class_id: int, db: AsyncSession = Depends(get_db)):
    if not await delete_asset_class(db, class_id):
        raise HTTPException(404, "Class not found")

# === Модели оборудования ===
@router_catalog.post("/models", response_model=AssetModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(data: AssetModelCreate, db: AsyncSession = Depends(get_db)):
    return await create_asset_model(db, data)

@router_catalog.get("/models", response_model=List[AssetModelResponse])
async def list_models(class_id: Optional[int] = None, skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)):
    return await get_asset_models(db, class_id, skip, limit)

@router_catalog.patch("/models/{model_id}", response_model=AssetModelResponse)
async def patch_model(model_id: int, data: AssetModelUpdate, db: AsyncSession = Depends(get_db)):
    res = await update_asset_model(db, model_id, data)
    if not res: raise HTTPException(404, "Model not found")
    return res

# Эндпоинт для получения статистики (Количество)
@router_catalog.get("/models/{model_id}/stats")
async def get_model_stats(model_id: int, db: AsyncSession = Depends(get_db)):
    """Возвращает динамически рассчитанное количество активов по модели"""
    return await get_catalog_stats_by_model(db, model_id)

# === Каталог (Связь Активов с Моделями) ===
@router_catalog.post("/items", response_model=AssetCatalogResponse, status_code=status.HTTP_201_CREATED)
async def add_catalog_item(data: AssetCatalogCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await add_to_catalog(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router_catalog.get("/items", response_model=List[AssetCatalogResponse])
async def list_catalog_items(model_id: Optional[int] = None, skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)):
    return await get_catalog_list(db, model_id, skip, limit)