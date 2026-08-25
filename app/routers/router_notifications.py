import asyncio
import json
import math
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from starlette.responses import StreamingResponse

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
from app.services.notifications import notification_manager

logger = logging.getLogger(__name__)

router_notifications = APIRouter(prefix="/notifications", tags=["Notifications"])


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

    # FastAPI сам сериализует через from_attributes
    return PaginatedNotificationResponse(
        items=list(notifications),
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
        unchecked_count=unread_count,
    )


@router_notifications.get("/my/grouped", response_model=List[NotificationGroupedItem])
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
            # FastAPI сам сериализует каждое уведомление
            notifications=list(notifications),
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
    # Возвращаем объект напрямую
    return notification


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
    """Отклонить назначение"""
    result = await decline_notification(db, notification_id, current_user.employee_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="Уведомление не найдено или не может быть отклонено"
        )
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


# @router_notifications.get("/stream")
# async def stream_notifications(employee = Depends(require_authorized_user)):
#     """ Эндпоинт потока уведомлений """
#     # Подключаем сотрудника к менеджеру
#     queue = await notification_manager.connect(employee.employee_id)
#     logger.debug(f"employee_id = {employee.employee_id}")
#
#     async def event_generator():
#         try:
#             while True:
#                 # Ждем новое сообщение в очереди
#                 data = await queue.get()
#                 # Формируем строку в формате SSE
#                 yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
#         except asyncio.CancelledError:
#             # Клиент отключился
#             notification_manager.disconnect(employee.employee_id)
#             raise
#
#     return StreamingResponse(
#         event_generator(),
#         media_type="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache",
#             "Connection": "keep-alive",
#             # "X-Accel-Buffering": "no" # Важно для Nginx, если он используется как прокси
#         }
#     )

@router_notifications.get("/stream")
async def stream_notifications(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Эндпоинт потока уведомлений: сначала история, потом новые события"""
    employee_id = current_user.employee_id

    # Подключаем сотрудника к менеджеру очередей
    queue = await notification_manager.connect(employee_id)
    logger.debug(f"Подключение к SSE: employee_id = {employee_id}")

    async def event_generator():
        try:
            # ШАГ 1: Получаем последние уведомления из БД (например, 50 штук)
            notifications, _ = await get_notifications_by_employee(
                db=db,
                employee_id=employee_id,
                page=1,
                page_size=50,
                only_unread=False,
            )

            # ШАГ 2: Отправляем каждое историческое уведомление в формате SSE
            for n in notifications:
                # Сериализуем SQLAlchemy модель через Pydantic схему
                n_dict = NotificationResponse.model_validate(n).model_dump()
                n_dict["source"] = "history"  # Метка для фронтенда
                yield f"data: {json.dumps(n_dict, ensure_ascii=False)}\n\n"

            # ШАГ 3: Переходим в режим ожидания новых событий в реальном времени
            while True:
                data = await queue.get()
                data["source"] = "realtime"   # Метка для фронтенда
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        except asyncio.CancelledError:
            # Клиент отключился (закрыл вкладку или оборвалось соединение)
            notification_manager.disconnect(employee_id)
            logger.debug(f"Клиент {employee_id} отключился от потока SSE")
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )