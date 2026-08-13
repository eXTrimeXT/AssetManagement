from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.database.connection import get_db
from app.database.assets.crud_asset_history import get_asset_history
from app.schemas.assets.AssetHistorySchemas import AssetHistoryResponse

router_asset_history = APIRouter(prefix="/asset-history", tags=["Asset History"])

@router_asset_history.get("/{asset_id}", response_model=List[AssetHistoryResponse])
async def read_asset_history(
        asset_id: int,
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db)
):
    """Получить историю изменений актива"""
    history = await get_asset_history(db, asset_id, skip=skip, limit=limit)
    if not history:
        raise HTTPException(status_code=404, detail="No history found for this asset")
    return history