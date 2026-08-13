from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database.connection import get_db
from app.database.analytics.crud_analytics import get_assets_by_status, get_assets_by_location, get_changes_heatmap, \
    get_user_activity, get_asset_lifecycle
from app.schemas.analytics.AnalyticsByGroup import CountByGroupResponse
from app.schemas.analytics.AssetLifecycle import AssetLifecycleEntry
from app.schemas.analytics.FieldChangeHeatmap import FieldChangeHeatmapResponse
from app.schemas.analytics.UserActivity import UserActivityResponse

router_analytics = APIRouter(prefix="/analytics", tags=["Analytics"])


@router_analytics.get("/assets/by-status", response_model=List[CountByGroupResponse])
async def assets_by_status(db: AsyncSession = Depends(get_db)):
    """Распределение активов по статусам"""
    return await get_assets_by_status(db)


@router_analytics.get("/assets/by-location", response_model=List[CountByGroupResponse])
async def assets_by_location(db: AsyncSession = Depends(get_db)):
    """Распределение активов по локациям"""
    return await get_assets_by_location(db)


@router_analytics.get("/changes/heatmap", response_model=List[FieldChangeHeatmapResponse])
async def changes_heatmap(db: AsyncSession = Depends(get_db)):
    """Какие поля активов меняются чаще всего"""
    return await get_changes_heatmap(db)


@router_analytics.get("/users/activity", response_model=List[UserActivityResponse])
async def user_activity(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Топ пользователей по активности (количество изменений)"""
    return await get_user_activity(db, limit=limit)


@router_analytics.get("/assets/lifecycle/{asset_id}", response_model=List[AssetLifecycleEntry])
async def asset_lifecycle(asset_id: int, db: AsyncSession = Depends(get_db)):
    """Полный timeline жизни конкретного актива"""
    history = await get_asset_lifecycle(db, asset_id)
    if not history:
        raise HTTPException(status_code=404, detail="No lifecycle data for this asset")
    return history