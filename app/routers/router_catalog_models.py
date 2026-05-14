from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.database.connection import get_db
from app.database.crud_catalog import create_asset_model, get_asset_models, update_asset_model, get_asset_model_by_id, \
    get_catalog_stats_by_model, delete_asset_model
from app.schemas.catalog.ModelSchemas import AssetModelCreate, AssetModelUpdate, AssetModelResponse
from app.service.auth.auth_service import require_authorized_user

router_catalog_models = APIRouter(prefix="/catalog/models", tags=["Asset Catalog Models"], dependencies=[Depends(require_authorized_user)])

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

@router_catalog_models.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(model_id: int, db: AsyncSession = Depends(get_db)):
    """
    Жестко удалить модель оборудования.
    Вернет 400 если модель используется в каталоге.
    """
    from sqlalchemy.exc import IntegrityError

    try:
        deleted = await delete_asset_model(db, model_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Model not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except ValueError as e:
        # Модель используется в каталоге
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError:
        # Защита на уровне БД (если вдруг пропустили проверку)
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Cannot delete model: foreign key constraint failed"
        )
