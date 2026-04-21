from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.database.connection import get_db
from app.database.crud_operations import get_history_by_inventory_id, get_history_by_asset_id
from app.schemas.operations.AssetOperationSchemas import AssetOperationResponse

router_assets_history = APIRouter(prefix="/assets", tags=["Assets History"])

@router_assets_history.get("/history/{inventory_id}", response_model=List[AssetOperationResponse])
async def get_asset_history_by_inventory_id(
        inventory_id: str, # Используем инвентарный номер вместо ID актива
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_db)
):
    """
    Получает полную историю операций по инвентарному номеру.
    Работает даже если актив был жестко удален.
    """
    # Можно проверить, существует ли вообще хоть какая-то история
    history = await get_history_by_inventory_id(db, inventory_id, skip, limit)

    if not history and skip == 0:
        raise HTTPException(status_code=404, detail="История для данного инвентарного номера не найдена")

    return history

@router_assets_history.get("/history{asset_id}", response_model=List[AssetOperationResponse])
async def get_asset_history_by_asset_id(
        asset_id: int,
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_db)
):
    """
    Получает полную историю операций по ID.
    Не работает если актив был жестко удален.
    """
    history = await get_history_by_asset_id(db, asset_id, skip, limit)
    if not history and skip == 0:
        raise HTTPException(status_code=404, detail="История для данного инвентарного номера не найдена")

    return history
