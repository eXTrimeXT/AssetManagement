from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from datetime import datetime, timedelta
import uuid

from app.models.assets.AssetHistory import AssetHistory
from app.models.assets.Asset import Asset


async def create_history_record(
        db: AsyncSession,
        asset_id: int,
        field_name: Optional[str],
        old_value: Optional[str],
        new_value: Optional[str],
        changed_by: str,
        action_type: str = "update",
        comment: Optional[str] = None,
        session_id: Optional[str] = None
) -> AssetHistory:
    """Создать запись в истории изменений"""
    history = AssetHistory(
        asset_id=asset_id,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        changed_by=changed_by,
        action_type=action_type,
        comment=comment,
        session_id=session_id
    )
    db.add(history)
    return history


async def get_asset_history(
        db: AsyncSession,
        asset_id: int,
        skip: int = 0,
        limit: int = 100
) -> List[AssetHistory]:
    """Получить историю изменений актива"""
    result = await db.execute(
        select(AssetHistory)
        .where(AssetHistory.asset_id == asset_id)
        .order_by(AssetHistory.changed_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def get_asset_history_grouped(
        db: AsyncSession,
        asset_id: int,
        skip: int = 0,
        limit: int = 50
) -> List[Dict[str, Any]]:
    """Получить историю, сгруппированную по session_id"""
    result = await db.execute(
        select(AssetHistory)
        .where(AssetHistory.asset_id == asset_id)
        .where(AssetHistory.session_id.isnot(None))
        .order_by(AssetHistory.changed_at.desc())
    )
    all_records = result.scalars().all()

    # Группируем по session_id
    grouped = {}
    for record in all_records:
        if record.session_id not in grouped:
            grouped[record.session_id] = {
                "session_id": record.session_id,
                "asset_id": record.asset_id,
                "changed_by": record.changed_by,
                "changer_full_name_ru": record.changer_full_name_ru,
                "changed_at": record.changed_at,
                "comment": record.comment,
                "changes": []
            }
        grouped[record.session_id]["changes"].append(record)

    # Сортируем по времени (новые сначала) и применяем пагинацию
    sorted_groups = sorted(
        grouped.values(),
        key=lambda x: x["changed_at"],
        reverse=True
    )

    return sorted_groups[skip:skip + limit]


async def get_history_with_filters(
        db: AsyncSession,
        asset_id: Optional[int] = None,
        changed_by: Optional[str] = None,
        action_type: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        session_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
) -> List[AssetHistory]:
    """Получить историю с фильтрами"""
    query = select(AssetHistory)

    filters = []
    if asset_id is not None:
        filters.append(AssetHistory.asset_id == asset_id)
    if changed_by is not None:
        filters.append(AssetHistory.changed_by == changed_by)
    if action_type is not None:
        filters.append(AssetHistory.action_type == action_type)
    if date_from is not None:
        filters.append(AssetHistory.changed_at >= date_from)
    if date_to is not None:
        filters.append(AssetHistory.changed_at <= date_to)
    if session_id is not None:
        filters.append(AssetHistory.session_id == session_id)

    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(AssetHistory.changed_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_history_stats(
        db: AsyncSession,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
) -> Dict[str, Any]:
    """Получить статистику по истории изменений"""
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Базовый фильтр по датам
    base_filter = []
    if date_from:
        base_filter.append(AssetHistory.changed_at >= date_from)
    if date_to:
        base_filter.append(AssetHistory.changed_at <= date_to)

    # Общее количество изменений
    total_query = select(func.count(AssetHistory.id))
    if base_filter:
        total_query = total_query.where(and_(*base_filter))
    total_result = await db.execute(total_query)
    total_changes = total_result.scalar()

    # Изменения за сегодня
    today_query = select(func.count(AssetHistory.id)).where(AssetHistory.changed_at >= today)
    if base_filter:
        today_query = today_query.where(and_(*base_filter))
    today_result = await db.execute(today_query)
    changes_today = today_result.scalar()

    # Изменения за неделю
    week_query = select(func.count(AssetHistory.id)).where(AssetHistory.changed_at >= week_ago)
    if base_filter:
        week_query = week_query.where(and_(*base_filter))
    week_result = await db.execute(week_query)
    changes_this_week = week_result.scalar()

    # Изменения за месяц
    month_query = select(func.count(AssetHistory.id)).where(AssetHistory.changed_at >= month_ago)
    if base_filter:
        month_query = month_query.where(and_(*base_filter))
    month_result = await db.execute(month_query)
    changes_this_month = month_result.scalar()

    # Самые активные пользователи (топ-10)
    users_query = (
        select(
            AssetHistory.changed_by,
            func.count(AssetHistory.id).label('count')
        )
        .group_by(AssetHistory.changed_by)
        .order_by(func.count(AssetHistory.id).desc())
        .limit(10)
    )
    if base_filter:
        users_query = users_query.where(and_(*base_filter))
    users_result = await db.execute(users_query)
    most_active_users = [
        {"employee_id": row[0], "count": row[1]}
        for row in users_result.all()
    ]

    # Самые изменяемые активы (топ-10)
    assets_query = (
        select(
            AssetHistory.asset_id,
            func.count(AssetHistory.id).label('count')
        )
        .group_by(AssetHistory.asset_id)
        .order_by(func.count(AssetHistory.id).desc())
        .limit(10)
    )
    if base_filter:
        assets_query = assets_query.where(and_(*base_filter))
    assets_result = await db.execute(assets_query)
    most_changed_assets = [
        {"asset_id": row[0], "count": row[1]}
        for row in assets_result.all()
    ]

    # Распределение по типам действий
    action_query = (
        select(
            AssetHistory.action_type,
            func.count(AssetHistory.id).label('count')
        )
        .group_by(AssetHistory.action_type)
    )
    if base_filter:
        action_query = action_query.where(and_(*base_filter))
    action_result = await db.execute(action_query)
    action_type_breakdown = {
        row[0]: row[1]
        for row in action_result.all()
    }

    return {
        "total_changes": total_changes,
        "changes_today": changes_today,
        "changes_this_week": changes_this_week,
        "changes_this_month": changes_this_month,
        "most_active_users": most_active_users,
        "most_changed_assets": most_changed_assets,
        "action_type_breakdown": action_type_breakdown
    }


async def compare_and_save_changes(
        db: AsyncSession,
        asset_id: int,
        old_data: dict,
        new_data: dict,
        changed_by: str,
        comment: Optional[str] = None
) -> List[AssetHistory]:
    """Сравнить старые и новые значения, сохранить изменения в историю"""
    changes = []

    # Генерируем session_id для группировки изменений
    session_id = str(uuid.uuid4())

    # Поля, которые нужно отслеживать
    tracked_fields = [
        'name', 'inventory_id', 'serial_number', 'comment',
        'date_issue', 'date_purchasing', 'model_id', 'model_name',
        'asset_type_id', 'parent_id',
        'asset_status_id',
        'parent_name', 'manufacturer_name',
        'vendor_name', 'os_name'
    ]

    for field in tracked_fields:
        old_val = old_data.get(field)
        new_val = new_data.get(field)

        # Конвертируем даты в строки для сравнения
        if hasattr(old_val, 'isoformat'):
            old_val = old_val.isoformat()
        if hasattr(new_val, 'isoformat'):
            new_val = new_val.isoformat()

        # Если значение изменилось
        if old_val != new_val:
            history = await create_history_record(
                db=db,
                asset_id=asset_id,
                field_name=field,
                old_value=str(old_val) if old_val is not None else None,
                new_value=str(new_val) if new_val is not None else None,
                changed_by=changed_by,
                action_type="update",
                comment=comment,
                session_id=session_id
            )
            changes.append(history)

    return changes


async def log_asset_creation(
        db: AsyncSession,
        asset_id: int,
        asset_data: dict,
        created_by: str
) -> AssetHistory:
    """Логирование создания актива"""
    return await create_history_record(
        db=db,
        asset_id=asset_id,
        field_name=None,
        old_value=None,
        new_value=str(asset_data),
        changed_by=created_by,
        action_type="create",
        comment="Создание актива"
    )


async def log_asset_deletion(
        db: AsyncSession,
        asset_id: int,
        deleted_by: str
) -> AssetHistory:
    """Логирование удаления актива"""
    return await create_history_record(
        db=db,
        asset_id=asset_id,
        field_name=None,
        old_value=None,
        new_value=None,
        changed_by=deleted_by,
        action_type="delete",
        comment="Удаление актива"
    )


async def log_assignment_change(
        db: AsyncSession,
        asset_id: int,
        employee_id: str,
        assignment_type: str,
        action: str,  # "assign" или "unassign"
        changed_by: str
) -> AssetHistory:
    """Логирование назначения/снятия пользователя"""
    return await create_history_record(
        db=db,
        asset_id=asset_id,
        field_name=assignment_type,
        old_value=None if action == "assign" else employee_id,
        new_value=employee_id if action == "assign" else None,
        changed_by=changed_by,
        action_type=action,
        comment=f"{'Назначение' if action == 'assign' else 'Снятие'} {assignment_type}: {employee_id}"
    )


async def log_location_change(
        db: AsyncSession,
        asset_id: int,
        old_location: Optional[dict],
        new_location: dict,
        changed_by: str
) -> AssetHistory:
    """Логирование изменения локации"""
    return await create_history_record(
        db=db,
        asset_id=asset_id,
        field_name="location",
        old_value=str(old_location) if old_location else None,
        new_value=str(new_location),
        changed_by=changed_by,
        action_type="move",
        comment="Перемещение актива"
    )