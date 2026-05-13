from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import pandas as pd
from starlette.responses import Response

from app.database.connection import get_db
from app.schemas.catalog.CatalogSchemas import AssetCatalogCreate, AssetCatalogResponse, AssetCatalogUpdate

from app.database.crud_catalog import add_to_catalog, get_catalog_list, get_catalog_item_by_id, delete_catalog_item, update_catalog_item
from app.service.auth.auth_service import require_authorized_user

router_catalog_items = APIRouter(prefix="/catalog/items", tags=["Asset Catalog Items"], dependencies=[Depends(require_authorized_user)])

# === Каталог (Связь Активов с Моделями) ===
@router_catalog_items.post("/", response_model=AssetCatalogResponse, status_code=status.HTTP_201_CREATED)
async def add_catalog_item(
        data: AssetCatalogCreate,
        current_user_id: int = 1,
        db: AsyncSession = Depends(get_db)):
    try:
        return await add_to_catalog(db, data, current_user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router_catalog_items.get("/", response_model=List[AssetCatalogResponse])
async def list_catalog_items(skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)):
    return await get_catalog_list(db, skip, limit)

@router_catalog_items.get("/{catalog_id}", response_model=AssetCatalogResponse)
async def get_catalog_item(catalog_id: int, db: AsyncSession = Depends(get_db)):
    item = await get_catalog_item_by_id(db, catalog_id)
    if not item:
        raise HTTPException(status_code=404, detail="Запись каталога не найдена")
    return item

@router_catalog_items.patch("/classes/{class_id}", response_model=AssetCatalogResponse)
async def patch_class(class_id: int, current_user_id: int, data: AssetCatalogUpdate, db: AsyncSession = Depends(get_db)):
    res = await update_catalog_item(db, class_id, *data, current_user_id=current_user_id)
    if not res: raise HTTPException(404, "Class not found")
    return res

@router_catalog_items.delete("/{catalog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_catalog_item_endpoint(
        catalog_id: int,
        current_user_id: int = 1, # ЗАГЛУШКА
        db: AsyncSession = Depends(get_db)
):
    success = await delete_catalog_item(db, catalog_id, current_user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Запись каталога не найдена")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
