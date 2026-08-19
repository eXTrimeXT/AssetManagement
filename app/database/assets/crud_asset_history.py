from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.assets.AssetHistory import AssetHistory
from datetime import datetime

async def create_history_record(
        db: AsyncSession,
        asset_id: int,
        field_name: str,
        old_value: Optional[str],
        new_value: Optional[str],
        changed_by: str
) -> AssetHistory:
    """Создать запись в истории изменений"""
    history = AssetHistory(
        asset_id=asset_id,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        changed_by=changed_by
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

async def compare_and_save_changes(
        db: AsyncSession,
        asset_id: int,
        old_data: dict,
        new_data: dict,
        changed_by: str
) -> List[AssetHistory]:
    """Сравнить старые и новые значения, сохранить изменения в историю"""
    changes = []

    # Поля, которые нужно отслеживать
    tracked_fields = [
        'name', 'inventory_id', 'serial_number', 'comment',
        'date_issue', 'date_purchasing', 'model_id', 'model_name',
        'asset_type_id', 'parent_id',
        # 'location_id',
        'asset_status_id',
        # 'responsible_by',
        # 'prepared_by', 'checked_by',
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
                changed_by=changed_by
            )
            changes.append(history)

    return changes