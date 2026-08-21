import math
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database.connection import get_db
from app.database.crud_notifications import (
    get_notifications_by_employee,
    get_notifications_grouped_by_asset,
    get_notification_by_id,
    mark_as_read,
    mark_all_as_read,
    decline_notification,
    delete_notification,
    delete_all_read,
    get_unread_count,
)
from app.schemas.notifications.NotificationSchemas import (
    NotificationResponse,
    PaginatedNotificationResponse,
    NotificationGroupedItem,
    NotificationDeclineResponse,
)
from app.services.auth.auth_service import require_authorized_user

logger = logging.getLogger(__name__)

router_notifications = APIRouter(prefix="/notifications", tags=["Notifications"])


def _notification_to_response(notification) -> NotificationResponse:
    """Преобразует Notification ORM в NotificationResponse"""
    asset = notification.asset
    initiator = notification.initiator

    initiator_name = None
    if initiator:
        parts = [p for p in [initiator.last_name, initiator.first_name, initiator.middle_name] if p]
        initiator_name = " ".join(parts) if parts else None

    return NotificationResponse(
        notification_id=notification.notification_id,
        employee_id=notification.employee_id,
        asset_id=notification.asset_id,
        event_type=notification.event_type,
        initiator_id=notification.initiator_id,
        status=notification.status,
        responded_at=notification.responded_at,
        created_at=notification.created_at,
        asset_name=asset.name if asset else None,
        asset_inventory_id=asset.inventory_id if asset else None,
        initiator_full_name=initiator_name,
    )


@router_notifications.get("/my", response_model=PaginatedNotificationResponse)
async def get_my_notifications(
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=200),
        only_unread: bool = Query(False),
        asset_id: Optional[int] = Query(None, description="Фильтр по активу"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Получить уведомления текущего пользователя с пагинацией"""
    notifications, total = await get_notifications_by_employee(
        db=db,
        employee_id=current_user.employee_id,
        page=page,
        page_size=page_size,
        only_unread=only_unread,
        asset_id=asset_id,
    )

    unread_count = await get_unread_count(db, current_user.employee_id)
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    items = [_notification_to_response(n) for n in notifications]

    return PaginatedNotificationResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
        unchecked_count=unread_count,
    )


@router_notifications.get("/my/grouped", response_model=list[NotificationGroupedItem])
async def get_my_notifications_grouped(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Получить уведомления, сгруппированные по активу"""
    grouped = await get_notifications_grouped_by_asset(db, current_user.employee_id)

    result = []
    for asset_id, notifications in grouped.items():
        asset = notifications[0].asset if notifications else None
        unread = sum(1 for n in notifications if n.status == "unread")

        result.append(NotificationGroupedItem(
            asset_id=asset_id,
            asset_name=asset.name if asset else None,
            asset_inventory_id=asset.inventory_id if asset else None,
            notifications=[_notification_to_response(n) for n in notifications],
            total=len(notifications),
            unread_count=unread,
        ))

    return result


@router_notifications.get("/my/unread-count")
async def get_my_unread_count(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Количество непрочитанных уведомлений"""
    count = await get_unread_count(db, current_user.employee_id)
    return {"count": count}


@router_notifications.patch("/{notification_id}/read", response_model=NotificationResponse)
async def read_notification(
        notification_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Пометить уведомление как прочитанное"""
    notification = await mark_as_read(db, notification_id, current_user.employee_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    return _notification_to_response(notification)


@router_notifications.patch("/my/read-all")
async def read_all_my_notifications(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Пометить все уведомления как прочитанные"""
    count = await mark_all_as_read(db, current_user.employee_id)
    return {"marked_as_read": count}


@router_notifications.post("/{notification_id}/decline", response_model=NotificationDeclineResponse)
async def decline_my_notification(
        notification_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Отклонить назначение (актив отвязывается, инициатор получает уведомление)"""
    result = await decline_notification(db, notification_id, current_user.employee_id)
    if not result:
        raise HTTPException(status_code=404, detail="Уведомление не найдено или не может быть отклонено")
    return NotificationDeclineResponse(
        message="Назначение отклонено",
        notification_id=notification_id,
    )


@router_notifications.delete("/{notification_id}", status_code=204)
async def delete_notification_endpoint(
        notification_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Удалить уведомление"""
    success = await delete_notification(db, notification_id, current_user.employee_id)
    if not success:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")


@router_notifications.delete("/my/clear-read")
async def clear_read_notifications(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Удалить все прочитанные уведомления"""
    count = await delete_all_read(db, current_user.employee_id)
    return {"deleted": count}