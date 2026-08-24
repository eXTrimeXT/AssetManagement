from typing import List, Any, Sequence
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, date

from app.models.assets.Asset import Asset
from app.models.assets.AssetStatus import AssetStatus
from app.models.assets.AssetHistory import AssetHistory
from app.models.assets.AssetType import AssetType
from app.models.assets.AssetAssignment import AssetAssignment
from app.models.assets.AssetWriteOff import AssetWriteOff
from app.models.map_assets.AssetPosition import AssetPosition
from app.models.map_assets.Workshop import Workshop


async def get_assets_by_status(db: AsyncSession) -> List[dict]:
    """Распределение активов по статусам"""
    query = (
        select(AssetStatus.status, func.count(Asset.asset_id).label("count"))
        .outerjoin(Asset, Asset.asset_status_id == AssetStatus.id)
        .group_by(AssetStatus.status)
    )
    result = await db.execute(query)
    return [{"name": row[0], "count": row[1]} for row in result.all()]

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

async def get_dashboard_summary(db: AsyncSession) -> dict:
    """Общая статистика для дашборда"""
    # Общее количество активов
    total_assets = await db.execute(select(func.count(Asset.asset_id)))
    total = total_assets.scalar()

    # Количество активов по типам
    by_type_query = (
        select(AssetType.name, func.count(Asset.asset_id).label("count"))
        .join(Asset, Asset.asset_type_id == AssetType.asset_type_id)
        .group_by(AssetType.name)
        .order_by(func.count(Asset.asset_id).desc())
    )
    by_type_result = await db.execute(by_type_query)
    by_type = [{"name": row[0], "count": row[1]} for row in by_type_result.all()]

    # Количество активов по workshop (через asset_positions)
    by_workshop_query = (
        select(Workshop.name, func.count(AssetPosition.asset_id).label("count"))
        .join(AssetPosition, AssetPosition.workshop_id == Workshop.workshop_id)
        .where(AssetPosition.is_active == True)
        .group_by(Workshop.name)
        .order_by(func.count(AssetPosition.asset_id).desc())
    )
    by_workshop_result = await db.execute(by_workshop_query)
    by_workshop = [{"name": row[0], "count": row[1]} for row in by_workshop_result.all()]

    # Топ-10 пользователей по количеству активов
    top_users_query = (
        select(AssetAssignment.employee_id, func.count(AssetAssignment.asset_id).label("count"))
        .where(AssetAssignment.end_date.is_(None))
        .group_by(AssetAssignment.employee_id)
        .order_by(func.count(AssetAssignment.asset_id).desc())
        .limit(10)
    )
    top_users_result = await db.execute(top_users_query)
    top_users = [{"employee_id": row[0], "count": row[1]} for row in top_users_result.all()]

    return {
        "total_assets": total,
        "by_type": by_type,
        "by_workshop": by_workshop,
        "top_users": top_users
    }

async def get_service_analytics(db: AsyncSession) -> dict:
    """Аналитика по обслуживанию активов"""
    today = date.today()
    week_from_now = today + timedelta(days=7)
    month_from_now = today + timedelta(days=30)

    # Активы с просроченным ТО
    overdue_query = (
        select(func.count(Asset.asset_id))
        .where(
            Asset.next_service < today,
            Asset.next_service.isnot(None)
        )
    )
    overdue_result = await db.execute(overdue_query)
    overdue_count = overdue_result.scalar()

    # Активы с ТО в ближайшие 7 дней
    upcoming_7_query = (
        select(func.count(Asset.asset_id))
        .where(
            Asset.next_service >= today,
            Asset.next_service <= week_from_now
        )
    )
    upcoming_7_result = await db.execute(upcoming_7_query)
    upcoming_7_count = upcoming_7_result.scalar()

    # Активы с ТО в ближайшие 30 дней
    upcoming_30_query = (
        select(func.count(Asset.asset_id))
        .where(
            Asset.next_service >= today,
            Asset.next_service <= month_from_now
        )
    )
    upcoming_30_result = await db.execute(upcoming_30_query)
    upcoming_30_count = upcoming_30_result.scalar()

    # Средний период обслуживания
    avg_period_query = (
        select(func.avg(Asset.service_period))
        .where(Asset.service_period.isnot(None))
    )
    avg_period_result = await db.execute(avg_period_query)
    avg_period = avg_period_result.scalar_one()

    return {
        "overdue_count": overdue_count,
        "upcoming_7_days": upcoming_7_count,
        "upcoming_30_days": upcoming_30_count,
        "avg_service_period": round(avg_period, 2) if avg_period else 0
    }

async def get_write_off_analytics(db: AsyncSession) -> dict:
    """Аналитика по списаниям"""
    # Количество заявок по статусам
    by_status_query = (
        select(AssetWriteOff.status, func.count(AssetWriteOff.write_off_id).label("count"))
        .group_by(AssetWriteOff.status)
    )
    by_status_result = await db.execute(by_status_query)
    by_status = [{"status": row[0], "count": row[1]} for row in by_status_result.all()]

    # Топ причин списаний
    by_type_query = (
        select(AssetWriteOff.write_off_type, func.count(AssetWriteOff.write_off_id).label("count"))
        .group_by(AssetWriteOff.write_off_type)
        .order_by(func.count(AssetWriteOff.write_off_id).desc())
    )
    by_type_result = await db.execute(by_type_query)
    by_type = [{"type": row[0], "count": row[1]} for row in by_type_result.all()]

    # === создаём переменную для date_trunc ===
    six_months_ago = datetime.now() - timedelta(days=180)
    month_expr = func.date_trunc('month', AssetWriteOff.requested_at)

    monthly_query = (
        select(
            month_expr.label('month'),
            func.count(AssetWriteOff.write_off_id).label('count')
        )
        .where(AssetWriteOff.requested_at >= six_months_ago)
        .group_by(month_expr)
        .order_by(month_expr)
    )
    monthly_result = await db.execute(monthly_query)
    monthly_trend = [
        {"month": row[0].strftime('%Y-%m'), "count": row[1]}
        for row in monthly_result.all()
    ]

    return {
        "by_status": by_status,
        "by_type": by_type,
        "monthly_trend": monthly_trend
    }

async def get_changes_trend(db: AsyncSession, days: int = 30) -> dict:
    """Тренд изменений за последние N дней"""
    start_date = datetime.now() - timedelta(days=days)

    # Изменения по дням
    daily_query = (
        select(
            func.date(AssetHistory.changed_at).label('date'),
            func.count(AssetHistory.id).label('count')
        )
        .where(AssetHistory.changed_at >= start_date)
        .group_by(func.date(AssetHistory.changed_at))
        .order_by(func.date(AssetHistory.changed_at))
    )
    daily_result = await db.execute(daily_query)
    daily_changes = [
        {"date": row[0].isoformat(), "count": row[1]}
        for row in daily_result.all()
    ]

    # Общее количество изменений за период
    total_query = (
        select(func.count(AssetHistory.id))
        .where(AssetHistory.changed_at >= start_date)
    )
    total_result = await db.execute(total_query)
    total_changes = total_result.scalar_one()

    # Среднее количество изменений в день
    avg_per_day = total_changes / days if days > 0 else 0

    return {
        "period_days": days,
        "total_changes": total_changes,
        "avg_per_day": round(avg_per_day, 2),
        "daily_changes": daily_changes
    }