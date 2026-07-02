from typing import Optional, Dict, Any, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime
from app.models.AssetOperation import AssetOperation

def _serialize_for_json(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_for_json(i) for i in obj]
    elif hasattr(obj, 'isoformat'): # date or datetime
        return obj.isoformat()
    else:
        return obj

async def create_operation_log(
        db: AsyncSession,
        asset_id: Optional[int],          # Теперь может быть None, если мы логируем что-то без привязки, но для активов будет ID
        operation_type: str,
        performed_by: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        comment: Optional[str] = None,
        # === НОВЫЕ ПАРАМЕТРЫ ДЛЯ СНАПШОТА ===
        inventory_id_snapshot: Optional[str] = None,
        name_snapshot: Optional[str] = None
) -> AssetOperation:
    """ Создает запись в журнале операций. """
    safe_old = _serialize_for_json(old_values) if old_values else None
    safe_new = _serialize_for_json(new_values) if new_values else None

    db_op = AssetOperation(
        asset_id=asset_id,
        inventory_id_snapshot=inventory_id_snapshot,
        name_snapshot=name_snapshot,
        operation_type=operation_type,
        performed_by=performed_by,
        old_values=safe_old,
        new_values=safe_new,
        comment=comment,
        timestamp=datetime.now()
    )
    db.add(db_op)
    await db.commit()
    await db.refresh(db_op)
    return db_op

async def get_history_by_asset_id(
        db: AsyncSession,
        asset_id: int,
        skip: int = 0,
        limit: int = 50
) -> Sequence[Any]:
    """ Получить историю по id, нужно для удобства """
    query = (
        select(AssetOperation)
        .where(AssetOperation.asset_id == asset_id) # Ищем по ID
        .options(selectinload(AssetOperation.performer))
        .order_by(AssetOperation.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()

async def get_history_by_inventory_id(
        db: AsyncSession,
        inventory_id: str,
        skip: int = 0,
        limit: int = 50
) -> Sequence[Any]:
    """ Получить историю по инвентарному номеру (если актив удален) """
    query = (
        select(AssetOperation)
        .where(AssetOperation.inventory_id_snapshot == inventory_id)
        .options(selectinload(AssetOperation.performer))
        .order_by(AssetOperation.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()