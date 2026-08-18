import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.database.crud_notifications import (
    get_notifications_by_employee,
    get_notification_by_id,
    mark_as_checked,
    mark_all_as_checked,
    delete_notification,
    delete_all_checked,
    get_unchecked_count,
)
from app.schemas.notifications.NotificationSchemas import NotificationResponse
from app.services.auth.auth_service import require_authorized_user

logger = logging.getLogger(__name__)

router_notifications = APIRouter(prefix="/notifications", tags=["Notifications"])


@router_notifications.get("/my", response_model=list[NotificationResponse])
async def get_my_notifications(
        page: int = Query(1, ge=1, description="Номер страницы"),
        page_size: int = Query(50, ge=1, le=200, description="Размер страницы"),
        only_unchecked: bool = Query(False, description="Только непрочитанные"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Получить уведомления текущего пользователя."""
    notifications, total = await get_notifications_by_employee(
        db=db,
        employee_id=current_user.employee_id,
        page=page,
        page_size=page_size,
        only_unchecked=only_unchecked,
    )
    return notifications


@router_notifications.get("/my/unchecked-count")
async def get_my_unchecked_count(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Количество непрочитанных уведомлений текущего пользователя."""
    count = await get_unchecked_count(db, current_user.employee_id)
    return {"count": count}


@router_notifications.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
        notification_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Получить одно уведомление по ID (только своё)."""
    notification = await get_notification_by_id(db, notification_id)
    if not notification or notification.employee_id != current_user.employee_id:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    return notification


@router_notifications.patch("/{notification_id}/check", response_model=NotificationResponse)
async def check_notification(
        notification_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Отметить уведомление как проверенное."""
    notification = await mark_as_checked(db, notification_id, current_user.employee_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    return notification


@router_notifications.patch("/my/check-all")
async def check_all_my_notifications(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Отметить все уведомления текущего пользователя как проверенные."""
    count = await mark_all_as_checked(db, current_user.employee_id)
    return {"marked_as_checked": count}


@router_notifications.delete("/{notification_id}", status_code=204)
async def delete_notification_endpoint(
        notification_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Удалить уведомление."""
    success = await delete_notification(db, notification_id, current_user.employee_id)
    if not success:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")


@router_notifications.delete("/my/clear-checked")
async def clear_checked_notifications(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Удалить все проверенные уведомления текущего пользователя."""
    count = await delete_all_checked(db, current_user.employee_id)
    return {"deleted": count}