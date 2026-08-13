from typing import List, Optional, Any, Sequence
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assets.Asset import Asset
from app.models.assets.AssetStatus import AssetStatus
from app.models.Location import Location
from app.models.assets.AssetHistory import AssetHistory


async def get_assets_by_status(db: AsyncSession) -> List[dict]:
    """Распределение активов по статусам"""
    query = (
        select(AssetStatus.status, func.count(Asset.asset_id).label("count"))
        .outerjoin(Asset, Asset.asset_status_id == AssetStatus.id)
        .group_by(AssetStatus.status)
    )
    result = await db.execute(query)
    return [{"name": row[0], "count": row[1]} for row in result.all()]


async def get_assets_by_location(db: AsyncSession) -> List[dict]:
    """Распределение активов по локациям"""
    query = (
        select(Location.name, func.count(Asset.asset_id).label("count"))
        .outerjoin(Asset, Asset.location_id == Location.location_id)
        .group_by(Location.name)
    )
    result = await db.execute(query)
    return [{"name": row[0] or "Без локации", "count": row[1]} for row in result.all()]


async def get_changes_heatmap(db: AsyncSession) -> List[dict]:
    """Какие поля меняются чаще всего (из истории)"""
    query = (
        select(AssetHistory.field_name, func.count(AssetHistory.id).label("change_count"))
        .group_by(AssetHistory.field_name)
        .order_by(func.count(AssetHistory.id).desc())
    )
    result = await db.execute(query)
    return [{"field_name": row[0], "change_count": row[1]} for row in result.all()]


async def get_user_activity(db: AsyncSession, limit: int = 20) -> List[dict]:
    """Топ пользователей по количеству изменений активов"""
    query = (
        select(AssetHistory.changed_by, func.count(AssetHistory.id).label("change_count"))
        .group_by(AssetHistory.changed_by)
        .order_by(func.count(AssetHistory.id).desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return [{"user_login": row[0], "change_count": row[1]} for row in result.all()]


async def get_asset_lifecycle(db: AsyncSession, asset_id: int) -> Sequence[Any]:
    """Полный timeline жизни конкретного актива"""
    result = await db.execute(
        select(AssetHistory)
        .where(AssetHistory.asset_id == asset_id)
        .order_by(AssetHistory.changed_at.asc())
    )
    return result.scalars().all()