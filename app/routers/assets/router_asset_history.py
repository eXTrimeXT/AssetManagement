from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Literal
from datetime import datetime

from app.database.connection import get_db
from app.database.assets.crud_asset_history import (
    get_asset_history,
    get_asset_history_grouped,
    get_history_with_filters,
    get_history_stats,
    migrate_old_history_records
)
from app.schemas.assets.AssetHistorySchemas import (
    AssetHistoryResponse,
    AssetHistoryGroupedResponse,
    AssetHistoryStatsResponse,
)
from app.services.auth.auth_service import require_authorized_user

router_asset_history = APIRouter(prefix="/asset-history", tags=["Asset History"])


@router_asset_history.get(
    "/filter",
    response_model=List[AssetHistoryResponse],
    summary="Получить историю с фильтрами / Get History with Filters",
    description=(
            "RU: Возвращает историю изменений активов с поддержкой расширенной фильтрации: "
            "по `asset_id`, пользователю `changed_by`, типу действия (`create`, `update`, `delete`, "
            "`assign`, `unassign`, `move`, `status_change`), диапазону дат (`date_from`, `date_to`) "
            "и идентификатору сессии `session_id`. Поддерживает пагинацию через параметры `skip` и `limit`. "
            "Если записей не найдено — возвращается ошибка 404. Требуется авторизация.\n\n"
            "EN: Returns the asset change history with advanced filtering support: "
            "by `asset_id`, user `changed_by`, action type (`create`, `update`, `delete`, "
            "`assign`, `unassign`, `move`, `status_change`), date range (`date_from`, `date_to`), "
            "and session identifier `session_id`. Supports pagination via `skip` and `limit` parameters. "
            "If no records are found, a 404 error is returned. Authorization is required."
    )
)
async def read_history_with_filters(
        asset_id: Optional[int] = Query(None),
        changed_by: Optional[str] = Query(None),
        action_type: Optional[Literal["create", "update", "delete", "assign", "unassign", "move", "status_change"]] = Query(None),
        date_from: Optional[datetime] = Query(None),
        date_to: Optional[datetime] = Query(None),
        session_id: Optional[str] = Query(None),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить историю изменений с различными фильтрами"""
    history = await get_history_with_filters(
        db=db,
        asset_id=asset_id,
        changed_by=changed_by,
        action_type=action_type if action_type else None,
        date_from=date_from,
        date_to=date_to,
        session_id=session_id,
        skip=skip,
        limit=limit
    )

    if not history:
        raise HTTPException(status_code=404, detail="Нет истории изменений")

    return history


@router_asset_history.get(
    "/stats",
    response_model=AssetHistoryStatsResponse,
    summary="Получить статистику по истории изменений / Get History Change Statistics",
    description=(
            "RU: Возвращает агрегированную статистику по истории изменений активов. "
            "Поддерживает фильтрацию по диапазону дат (`date_from`, `date_to`). "
            "Полезно для аналитики и дашбордов. Требуется авторизация.\n\n"
            "EN: Returns aggregated statistics on asset change history. "
            "Supports filtering by date range (`date_from`, `date_to`). "
            "Useful for analytics and dashboards. Authorization is required."
    )
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
    summary="Получить историю изменений актива / Get Asset Change History",
    description=(
            "RU: Возвращает историю изменений конкретного актива по его `asset_id`. "
            "Поддерживает пагинацию через параметры `skip` и `limit`. "
            "Записи отсортированы по дате изменения. Требуется авторизация.\n\n"
            "EN: Returns the change history of a specific asset by its `asset_id`. "
            "Supports pagination via `skip` and `limit` parameters. "
            "Records are sorted by change date. Authorization is required."
    )
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
    summary="Получить историю, сгруппированную по операциям / Get History Grouped by Operations",
    description=(
            "RU: Возвращает историю изменений конкретного актива, сгруппированную по `session_id`. "
            "Позволяет отобразить связанные изменения (например, несколько полей, изменённых в рамках одной операции) "
            "в виде единой записи. Поддерживает пагинацию через параметры `skip` и `limit`. Требуется авторизация.\n\n"
            "EN: Returns the change history of a specific asset, grouped by `session_id`. "
            "Allows displaying related changes (e.g., multiple fields modified within a single operation) "
            "as a single record. Supports pagination via `skip` and `limit` parameters. Authorization is required."
    )
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


@router_asset_history.post(
    "/migrate-old-records",
    summary="Одноразовая миграция старых записей истории / One-time Migration of Old History Records",
    description=(
            "RU: Запускает одноразовый процесс миграции старых записей истории. "
            "Преобразует ID в названия и переводит `field_name` на русский язык для устаревших записей. "
            "Процесс разбит на пакеты (параметр `batch_size`), чтобы не блокировать БД надолго. "
            "**Внимание:** запускайте только один раз! Требуется авторизация (в идеале — роль администратора).\n\n"
            "EN: Triggers a one-time migration process for old history records. "
            "Converts IDs to names and translates `field_name` to Russian for legacy records. "
            "The process is split into batches (via the `batch_size` parameter) to avoid long DB locks. "
            "**Warning:** run only once! Authorization is required (ideally, an admin role)."
    )
)
async def trigger_history_migration(
        batch_size: int = Query(500, ge=100, le=2000, description="Размер пакета для обработки"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user) # В идеале здесь должна быть проверка на админа
):
    """
    Запускает процесс обновления исторических данных.
    Процесс разбит на пакеты, чтобы не блокировать БД надолго.
    """
    try:
        result = await migrate_old_history_records(db, batch_size=batch_size)
        return {
            "message": "Миграция успешно завершена",
            "records_updated": result["total_updated"]
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при миграции: {str(e)}")