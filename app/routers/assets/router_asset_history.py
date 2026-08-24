from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime

from app.database.connection import get_db
from app.database.assets.crud_asset_history import (
    get_asset_history,
    get_asset_history_grouped,
    get_history_with_filters,
    get_history_stats
)
from app.schemas.assets.AssetHistorySchemas import (
    AssetHistoryResponse,
    AssetHistoryGroupedResponse,
    AssetHistoryStatsResponse,
    ActionType
)
from app.services.auth.auth_service import require_authorized_user

router_asset_history = APIRouter(prefix="/asset-history", tags=["Asset History"])


@router_asset_history.get(
    "/filter",
    response_model=List[AssetHistoryResponse],
    summary="Получить историю с фильтрами"
)
async def read_history_with_filters(
        asset_id: Optional[int] = Query(None),
        changed_by: Optional[str] = Query(None),
        action_type: Optional[ActionType] = Query(None),
        date_from: Optional[datetime] = Query(None),
        date_to: Optional[datetime] = Query(None),
        session_id: Optional[str] = Query(None),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить историю изменений с различными фильтрами"""
    return await get_history_with_filters(
        db=db,
        asset_id=asset_id,
        changed_by=changed_by,
        action_type=action_type,
        date_from=date_from,
        date_to=date_to,
        session_id=session_id,
        skip=skip,
        limit=limit
    )


@router_asset_history.get(
    "/stats",
    response_model=AssetHistoryStatsResponse,
    summary="Получить статистику по истории изменений"
)
async def read_history_stats(
        date_from: Optional[datetime] = Query(None),
        date_to: Optional[datetime] = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить статистику по истории изменений"""
    return await get_history_stats(db, date_from=date_from, date_to=date_to)


@router_asset_history.get(
    "/{asset_id}",
    response_model=List[AssetHistoryResponse],
    summary="Получить историю изменений актива"
)
async def read_asset_history(
        asset_id: int,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить историю изменений актива"""
    history = await get_asset_history(db, asset_id, skip=skip, limit=limit)
    return history


@router_asset_history.get(
    "/{asset_id}/grouped",
    response_model=List[AssetHistoryGroupedResponse],
    summary="Получить историю, сгруппированную по операциям"
)
async def read_asset_history_grouped(
        asset_id: int,
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить историю изменений, сгруппированную по session_id"""
    return await get_asset_history_grouped(db, asset_id, skip=skip, limit=limit)