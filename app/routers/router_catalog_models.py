from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import pandas as pd

from app.database.connection import get_db
from app.database.crud_catalog import create_asset_model, get_asset_models, update_asset_model, get_asset_model_by_id, get_catalog_stats_by_model
from app.schemas.catalog.ModelSchemas import AssetModelCreate, AssetModelUpdate, AssetModelResponse

router_catalog_models = APIRouter(prefix="/catalog/models", tags=["Asset Catalog Models"])

# === Модели оборудования ===
@router_catalog_models.post("/", response_model=AssetModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(data: AssetModelCreate, db: AsyncSession = Depends(get_db)):
    return await create_asset_model(db, data)

@router_catalog_models.get("/{model_id}", response_model=AssetModelResponse)
async def get_model(model_id: int, db: AsyncSession = Depends(get_db)):
    obj = await get_asset_model_by_id(db, model_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Model not found")
    return obj

@router_catalog_models.get("/", response_model=List[AssetModelResponse])
async def list_models(class_id: Optional[int] = None, skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)):
    return await get_asset_models(db, class_id, skip, limit)

@router_catalog_models.patch("/{model_id}", response_model=AssetModelResponse)
async def patch_model(model_id: int, data: AssetModelUpdate, db: AsyncSession = Depends(get_db)):
    res = await update_asset_model(db, model_id, data)
    if not res: raise HTTPException(404, "Model not found")
    return res

# Эндпоинт для получения статистики (Количество)
@router_catalog_models.get("/models/{model_id}/stats")
async def get_model_stats(model_id: int, db: AsyncSession = Depends(get_db)):
    """Возвращает динамически рассчитанное количество активов по модели"""
    return await get_catalog_stats_by_model(db, model_id)
