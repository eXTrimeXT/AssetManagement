import asyncio
import json
import math
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Literal

from starlette.responses import StreamingResponse

from app.database.connection import get_db
from app.database.crud_notifications import (
    get_notifications_by_employee,
    get_notifications_grouped_by_asset,
    mark_as_read,
    mark_all_as_read,
    delete_notification,
    delete_all_read,
    get_unread_count, get_notification_counts, get_notification_counts_grouped
)
from app.schemas.notifications.NotificationSchemas import (
    NotificationResponse,
    PaginatedNotificationResponse,
    NotificationGroupedItem,
)
from app.services.auth.auth_service import require_authorized_user
from app.services.notifications import notification_manager

logger = logging.getLogger(__name__)

router_notifications = APIRouter(prefix="/notifications", tags=["Notifications"])


@router_notifications.get(
    "/my",
    summary="Получить мои уведомления / Get My Notifications",
    description=(
            "RU: Возвращает пагинированный список уведомлений текущего пользователя с поддержкой "
            "расширенной фильтрации: по `asset_id`, `session_id`, направлению (`incoming`, `outgoing`, `all`), "
            "типу уведомления (`asset`, `session`, `all`) и параметру `only_unread`. "
            "Также возвращает счётчики прочитанных и непрочитанных уведомлений. "
            "Computed-поля (`event_type_ru`, `direction_ru`, `status_ru`) вычисляются с учётом роли текущего пользователя. "
            "Требуется авторизация.\n\n"
            "EN: Returns a paginated list of notifications for the current user with advanced filtering support: "
            "by `asset_id`, `session_id`, direction (`incoming`, `outgoing`, `all`), "
            "notification type (`asset`, `session`, `all`), and the `only_unread` parameter. "
            "Also returns counters of read and unread notifications. "
            "Computed fields (`event_type_ru`, `direction_ru`, `status_ru`) are calculated based on the current user's role. "
            "Authorization is required."
    )
)
async def get_my_notifications(
        page: int = Query(1, ge=1),
        page_size: int = Query(200, ge=1, le=200),
        only_unread: bool = Query(False, description="Показывать только непрочитанные"),
        asset_id: Optional[int] = Query(None, description="Фильтр по ID актива"),
        session_id: Optional[int] = Query(None, description="Фильтр по ID сессии инвентаризации"),
        direction: Literal["incoming", "outgoing", "all"] = Query(
            "all", description="incoming (входящие), outgoing (исходящие) или all (все)"
        ),
        notification_type: Literal["all", "asset", "session"] = Query(
            "all", description="Тип уведомления: all, asset или session"
        ),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Получение всех видов уведомлений с параметрами.

    ВАЖНО: декоратор НЕ использует response_model, потому что FastAPI при
    повторной валидации создаёт NotificationResponse без context={"viewer_id": ...},
    из-за чего computed-поля (event_type_ru, direction_ru и т.д.) теряют
    информацию о роли зрителя. Поэтому сериализуем вручную и возвращаем dict.
    """
    employee_id = current_user.employee_id

    notifications, total = await get_notifications_by_employee(
        db=db,
        employee_id=employee_id,
        page=page,
        page_size=page_size,
        only_unread=only_unread,
        asset_id=asset_id,
        session_id=session_id,
        direction=direction,
        notification_type=notification_type,
    )

    counts = await get_notification_counts(db, employee_id)
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    # Один проход валидации с context — здесь вычисляются event_type_ru,
    # direction_ru, status_ru строго по роли текущего пользователя.
    items = [
        NotificationResponse.model_validate(
            n,
            context={"viewer_id": employee_id, "direction": direction},
        )
        for n in notifications
    ]

    # Сериализуем один раз вручную, чтобы FastAPI не запускал повторную
    # валидацию через response_model (без context).
    return PaginatedNotificationResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
        unchecked_count=counts["unchecked_count"],
        checked_count=counts["checked_count"],
    ).model_dump(mode="json")


@router_notifications.get(
    "/stream",
    summary="Стрим уведомлений через SSE / Stream Notifications via SSE",
    description=(
            "RU: Эндпоинт Server-Sent Events (SSE) для получения уведомлений в реальном времени. "
            "При подключении отправляется текущее состояние (источник `initial`), "
            "затем при каждом изменении — обновлённое состояние (источник `update`). "
            "Поддерживает фильтрацию по `asset_id`, `session_id`, направлению и типу уведомления. "
            "Соединение поддерживается до отключения клиента. Требуется авторизация.\n\n"
            "EN: Server-Sent Events (SSE) endpoint for receiving notifications in real time. "
            "Upon connection, the current state is sent (source `initial`), "
            "then on each change — the updated state (source `update`). "
            "Supports filtering by `asset_id`, `session_id`, direction, and notification type. "
            "The connection is maintained until the client disconnects. Authorization is required."
    )
)
async def stream_notifications(
        asset_id: Optional[int] = Query(None, description="Фильтр по ID актива"),
        session_id: Optional[int] = Query(None, description="Фильтр по ID сессии инвентаризации"),
        direction: Literal["incoming", "outgoing", "all"] = Query("all", description="incoming, outgoing или all"),
        notification_type: Literal["all", "asset", "session"] = Query("all", description="Тип уведомления: all, asset или session"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    employee_id = current_user.employee_id
    queue = await notification_manager.connect(employee_id)
    logger.debug(f"Подключение к SSE: employee_id = {employee_id}, direction = {direction}")

    async def get_full_state():
        notifications, total = await get_notifications_by_employee(
            db=db,
            employee_id=employee_id,
            page=1,
            page_size=200,
            only_unread=False,
            asset_id=asset_id,
            session_id=session_id,
            direction=direction,
            notification_type=notification_type,
        )

        counts = await get_notification_counts(db, employee_id)
        total_pages = math.ceil(total / 100) if total > 0 else 0

        # Один проход валидации с context={"viewer_id": ...}.
        # Никакого model_dump здесь — сериализация произойдёт ниже,
        # когда FastAPI/StreamingResponse будет писать JSON-строку.
        items = [
            NotificationResponse.model_validate(
                n,
                context={"viewer_id": employee_id, "direction": direction},
            )
            for n in notifications
        ]

        # Сериализуем через PaginatedNotificationResponse один раз вручную,
        # чтобы гарантированно не запускать повторную валидацию без context.
        paginated = PaginatedNotificationResponse(
            items=items,
            total=total,
            page=1,
            page_size=100,
            total_pages=total_pages,
            has_next=1 < total_pages,
            has_previous=False,
            unchecked_count=counts["unchecked_count"],
            checked_count=counts["checked_count"],
        )

        return paginated.model_dump(mode="json")

    async def event_generator():
        try:
            initial_state = await get_full_state()
            initial_state["source"] = "initial"
            yield f"data: {json.dumps(initial_state, ensure_ascii=False)}\n\n"

            while True:
                _ = await queue.get()
                updated_state = await get_full_state()
                updated_state["source"] = "update"
                yield f"data: {json.dumps(updated_state, ensure_ascii=False)}\n\n"

        except asyncio.CancelledError:
            notification_manager.disconnect(employee_id, queue)
            logger.debug(f"Клиент {employee_id} отключился от потока SSE")
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router_notifications.get(
    "/my/grouped",
    summary="Получить уведомления, сгруппированные по активу / Get Notifications Grouped by Asset",
    description=(
            "RU: Возвращает список уведомлений текущего пользователя, сгруппированных по `asset_id`. "
            "Для каждой группы указывается информация об активе (название, инвентарный номер), "
            "общее количество уведомлений и количество непрочитанных. "
            "Computed-поля вычисляются с учётом роли текущего пользователя. "
            "Требуется авторизация.\n\n"
            "EN: Returns a list of notifications for the current user, grouped by `asset_id`. "
            "For each group, asset information is provided (name, inventory number), "
            "total number of notifications, and the number of unread ones. "
            "Computed fields are calculated based on the current user's role. "
            "Authorization is required."
    )
)
async def get_my_notifications_grouped(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Получить уведомления, сгруппированные по активу.

    ВАЖНО: декоратор НЕ использует response_model=List[NotificationGroupedItem],
    потому что FastAPI при повторной валидации создаёт вложенные
    NotificationResponse без context={"viewer_id": ...}, из-за чего
    computed-поля (event_type_ru, direction_ru и т.д.) вычисляются от
    «анонимного» зрителя и получают дефолтные значения.
    """
    employee_id = current_user.employee_id
    grouped = await get_notifications_grouped_by_asset(db, employee_id)

    result = []
    for asset_id, notifications in grouped.items():
        asset = notifications[0].asset if notifications else None
        unread = sum(1 for n in notifications if n.status == "unread")

        # Явно валидируем каждое уведомление с context — как в /my.
        validated_notifications = [
            NotificationResponse.model_validate(
                n,
                context={"viewer_id": employee_id, "direction": "all"},
            )
            for n in notifications
        ]

        result.append(
            NotificationGroupedItem(
                asset_id=asset_id,
                asset_name=asset.name if asset else None,
                asset_inventory_id=asset.inventory_id if asset else None,
                notifications=validated_notifications,
                total=len(notifications),
                unread_count=unread,
            )
        )

    # Сериализуем один раз вручную, чтобы FastAPI не запускал повторную
    # валидацию через response_model (без context).
    return [item.model_dump(mode="json") for item in result]


@router_notifications.get(
    "/my/unread-count",
    summary="Получить количество непрочитанных уведомлений / Get Unread Notifications Count",
    description=(
            "RU: Возвращает количество непрочитанных уведомлений для текущего авторизованного пользователя. "
            "Полезно для отображения бейджа с числом новых уведомлений в интерфейсе. "
            "Требуется авторизация.\n\n"
            "EN: Returns the number of unread notifications for the current authenticated user. "
            "Useful for displaying a badge with the number of new notifications in the UI. "
            "Authorization is required."
    )
)
async def get_my_unread_count(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Количество непрочитанных уведомлений"""
    count = await get_unread_count(db, current_user.employee_id)
    return {"count": count}


@router_notifications.get(
    "/my/counts",
    summary="Получить счётчики уведомлений по группам / Get Notification Counts by Groups",
    description=(
            "RU: Возвращает счётчики уведомлений, сгруппированные по `asset_id` и `session_id`. "
            "Поддерживает фильтрацию по направлению (`incoming`, `outgoing`, `all`), "
            "идентификатору актива и идентификатору сессии инвентаризации. "
            "Полезно для отображения сводной информации в UI. Требуется авторизация.\n\n"
            "EN: Returns notification counts grouped by `asset_id` and `session_id`. "
            "Supports filtering by direction (`incoming`, `outgoing`, `all`), "
            "asset identifier, and inventory session identifier. "
            "Useful for displaying summary information in the UI. Authorization is required."
    )
)
async def get_my_notification_counts_grouped(
        asset_id: Optional[int] = Query(None, description="Фильтр по ID актива"),
        session_id: Optional[int] = Query(None, description="Фильтр по ID сессии инвентаризации"),
        direction: Literal["incoming", "outgoing", "all"] = Query(
            "all",
            description="incoming (входящие), outgoing (исходящие) или all (все)"
        ),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """
    Получить счётчики уведомлений, сгруппированные по asset_id и session_id.
    """
    counts = await get_notification_counts_grouped(
        db=db,
        employee_id=current_user.employee_id,
        direction=direction,
        asset_id=asset_id,
        session_id=session_id
    )
    return counts


@router_notifications.patch(
    "/{notification_id}/read",
    summary="Пометить уведомление как прочитанное / Mark Notification as Read",
    description=(
            "RU: Помечает указанное уведомление как прочитанное для текущего пользователя. "
            "Возвращает обновлённые данные уведомления с вычисленными computed-полями "
            "с учётом роли текущего пользователя. "
            "Если уведомление не найдено — возвращается ошибка 404. "
            "Требуется авторизация.\n\n"
            "EN: Marks the specified notification as read for the current user. "
            "Returns the updated notification data with computed fields "
            "calculated based on the current user's role. "
            "If the notification is not found, a 404 error is returned. "
            "Authorization is required."
    )
)
async def read_notification(
        notification_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    notification = await mark_as_read(db, notification_id, current_user.employee_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")

    return NotificationResponse.model_validate(
        notification,
        context={"viewer_id": current_user.employee_id, "direction": "all"},
    ).model_dump(mode="json")


@router_notifications.patch(
    "/my/read-all",
    summary="Пометить все уведомления как прочитанные / Mark All Notifications as Read",
    description=(
            "RU: Помечает все уведомления текущего пользователя как прочитанные. "
            "Возвращает количество уведомлений, которые были помечены как прочитанные. "
            "Требуется авторизация.\n\n"
            "EN: Marks all notifications of the current user as read. "
            "Returns the number of notifications that were marked as read. "
            "Authorization is required."
    )
)
async def read_all_my_notifications(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Пометить все уведомления как прочитанные"""
    count = await mark_all_as_read(db, current_user.employee_id)
    return {"marked_as_read": count}


@router_notifications.delete(
    "/{notification_id}",
    status_code=204,
    summary="Удалить уведомление / Delete Notification",
    description=(
            "RU: Удаляет указанное уведомление (мягкое или жёсткое удаление в зависимости от роли и статуса). "
            "Удалять можно только свои уведомления. "
            "Если уведомление не найдено или у пользователя нет прав на удаление — возвращается ошибка 404. "
            "При успешном удалении возвращается статус 204 (No Content). "
            "Требуется авторизация.\n\n"
            "EN: Deletes the specified notification (soft or hard deletion depending on role and status). "
            "Only own notifications can be deleted. "
            "If the notification is not found or the user has no deletion rights, a 404 error is returned. "
            "On successful deletion, a 204 (No Content) status is returned. "
            "Authorization is required."
    )
)
async def delete_notification_endpoint(
        notification_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Удалить уведомление (мягкое или жесткое в зависимости от роли и статуса)"""
    success = await delete_notification(db, notification_id, current_user.employee_id)
    if not success:
        raise HTTPException(status_code=404, detail="Уведомление не найдено или нет прав на удаление")


@router_notifications.delete(
    "/my/clear-read",
    summary="Удалить все прочитанные уведомления / Clear All Read Notifications",
    description=(
            "RU: Мягко удаляет все прочитанные уведомления текущего пользователя. "
            "Возвращает количество удалённых уведомлений. "
            "Непрочитанные уведомления остаются нетронутыми. "
            "Требуется авторизация.\n\n"
            "EN: Soft-deletes all read notifications of the current user. "
            "Returns the number of deleted notifications. "
            "Unread notifications remain untouched. "
            "Authorization is required."
    )
)
async def clear_read_notifications(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Мягко удалить все прочитанные уведомления для текущего пользователя"""
    count = await delete_all_read(db, current_user.employee_id)
    return {"deleted": count}