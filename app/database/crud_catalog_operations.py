from typing import Optional, Dict, Any, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime
from app.models.CatalogOperation import CatalogOperation

def _serialize_for_json(obj: Any) -> Any:
    """Рекурсивно преобразует date/datetime в строки для JSON"""
    if isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_for_json(i) for i in obj]
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        return obj

async def create_catalog_operation_log(
        db: AsyncSession,
        catalog_id: int,
        operation_type: str,
        performed_by: Optional[int] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        comment: Optional[str] = None,
        # Снимки данных
        asset_inventory_id_snapshot: Optional[str] = None,
        model_name_snapshot: Optional[str] = None,
        class_name_snapshot: Optional[str] = None
) -> CatalogOperation:
    """
    Создает запись в журнале операций каталога.
    """
    safe_old = _serialize_for_json(old_values) if old_values else None
    safe_new = _serialize_for_json(new_values) if new_values else None

    db_op = CatalogOperation(
        catalog_id=catalog_id,
        asset_inventory_id_snapshot=asset_inventory_id_snapshot,
        model_name_snapshot=model_name_snapshot,
        class_name_snapshot=class_name_snapshot,
        operation_type=operation_type,
        performed_by=performed_by,
        old_values=safe_old,
        new_values=safe_new,
        comment=comment,
        timestamp=datetime.utcnow()
    )
    db.add(db_op)
    await db.commit()
    await db.refresh(db_op)
    return db_op

async def get_catalog_history(
        db: AsyncSession,
        catalog_id: int,
        skip: int = 0,
        limit: int = 50
) -> Sequence[Any]:
    """
    Получает историю операций для конкретной записи каталога.
    """
    query = (
        select(CatalogOperation)
        .where(CatalogOperation.catalog_id == catalog_id)
        .options(selectinload(CatalogOperation.performer))
        .order_by(CatalogOperation.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()