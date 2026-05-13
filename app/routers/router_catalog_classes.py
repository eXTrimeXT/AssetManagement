from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import pandas as pd

from app.database.connection import get_db
from app.schemas.catalog.ClassSchemas import AssetClassCreate, AssetClassUpdate, AssetClassResponse

from app.database.crud_catalog import create_asset_class, get_asset_classes, update_asset_class, delete_asset_class, get_asset_class_by_id
from app.service.auth.auth_service import require_authorized_user

router_catalog_classes = APIRouter(prefix="/catalog", tags=["Asset Catalog Classes"], dependencies=[Depends(require_authorized_user)])

# === Классы оборудования ===
@router_catalog_classes.post("/classes", response_model=AssetClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(data: AssetClassCreate, db: AsyncSession = Depends(get_db)):
    return await create_asset_class(db, data)

@router_catalog_classes.get("/classes/{class_id}", response_model=AssetClassResponse)
async def get_class(class_id: int, db: AsyncSession = Depends(get_db)):
    obj = await get_asset_class_by_id(db, class_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Class not found")
    return obj

@router_catalog_classes.get("/classes", response_model=List[AssetClassResponse])
async def list_classes(skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)):
    # Теперь эта функция возвращает объекты с подгруженными связями
    return await get_asset_classes(db, skip, limit)

@router_catalog_classes.patch("/classes/{class_id}", response_model=AssetClassResponse)
async def patch_class(class_id: int, data: AssetClassUpdate, db: AsyncSession = Depends(get_db)):
    res = await update_asset_class(db, class_id, data)
    if not res: raise HTTPException(404, "Class not found")
    return res

@router_catalog_classes.delete("/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(class_id: int, db: AsyncSession = Depends(get_db)):
    if not await delete_asset_class(db, class_id):
        raise HTTPException(404, "Class not found")