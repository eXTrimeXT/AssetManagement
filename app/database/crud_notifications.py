from typing import Optional, Tuple, Sequence
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.notifications.Notification import (
    Notification, NotificationEventType, NotificationStatus
)
from app.models.assets.Asset import Asset
from app.models.assets.AssetAssignment import AssetAssignment


async def create_notification(
        db: AsyncSession,
        employee_id: str,
        asset_id: int,
        event_type: str,
        initiator_id: Optional[str] = None,
) -> Notification:
    """Создать уведомление"""
    notification = Notification(
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=event_type,
        initiator_id=initiator_id,
        status=NotificationStatus.UNREAD,
    )
    db.add(notification)
    await db.flush()
    return notification

async def get_notifications_by_employee(
        db: AsyncSession,
        employee_id: str,
        page: int = 1,
        page_size: int = 50,
        only_unread: bool = False,
        asset_id: Optional[int] = None,
) -> Tuple[Sequence[Notification], int]:
    """Получить уведомления сотрудника с пагинацией"""
    # Подсчёт
    count_query = (
        select(func.count(Notification.notification_id))
        .where(Notification.employee_id == employee_id)
    )
    if only_unread:
        count_query = count_query.where(Notification.status == NotificationStatus.UNREAD)
    if asset_id is not None:
        count_query = count_query.where(Notification.asset_id == asset_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Данные
    query = (
        select(Notification)
        .options(
            selectinload(Notification.asset),
            selectinload(Notification.initiator),
        )
        .where(Notification.employee_id == employee_id)
    )
    if only_unread:
        query = query.where(Notification.status == NotificationStatus.UNREAD)
    if asset_id is not None:
        query = query.where(Notification.asset_id == asset_id)

    query = query.order_by(Notification.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    notifications = result.scalars().all()

    return notifications, total


async def get_notifications_grouped_by_asset(
        db: AsyncSession,
        employee_id: str,
) -> list:
    """Получить уведомления, сгруппированные по asset_id"""
    result = await db.execute(
        select(Notification)
        .options(
            selectinload(Notification.asset),
            selectinload(Notification.initiator),
        )
        .where(Notification.employee_id == employee_id)
        .order_by(Notification.created_at.desc())
    )
    notifications = result.scalars().all()

    # Группируем
    grouped = {}
    for n in notifications:
        if n.asset_id not in grouped:
            grouped[n.asset_id] = []
        grouped[n.asset_id].append(n)

    return grouped


async def get_notification_by_id(
        db: AsyncSession,
        notification_id: int,
) -> Optional[Notification]:
    """Получить уведомление по ID"""
    result = await db.execute(
        select(Notification)
        .options(
            selectinload(Notification.asset),
            selectinload(Notification.initiator),
        )
        .where(Notification.notification_id == notification_id)
    )
    return result.scalar_one_or_none()


async def mark_as_read(
        db: AsyncSession,
        notification_id: int,
        employee_id: str,
) -> Optional[Notification]:
    """Пометить уведомление как прочитанное"""
    notification = await get_notification_by_id(db, notification_id)
    if not notification or notification.employee_id != employee_id:
        return None

    notification.status = NotificationStatus.READ
    await db.commit()
    await db.refresh(notification)
    return notification


async def mark_all_as_read(
        db: AsyncSession,
        employee_id: str,
) -> int:
    """Пометить все уведомления как прочитанные"""
    result = await db.execute(
        select(Notification)
        .where(
            Notification.employee_id == employee_id,
            Notification.status == NotificationStatus.UNREAD,
            )
    )
    notifications = result.scalars().all()

    count = 0
    for n in notifications:
        n.status = NotificationStatus.READ
        count += 1

    if count > 0:
        await db.commit()
    return count


async def decline_notification(
        db: AsyncSession,
        notification_id: int,
        employee_id: str,
) -> Optional[dict]:
    """
    Отклонить назначение.
    1. Помечает уведомление как declined
    2. Закрывает привязку в asset_assignments
    3. Создаёт ответное уведомление инициатору
    """
    notification = await get_notification_by_id(db, notification_id)
    if not notification or notification.employee_id != employee_id:
        return None

    # Проверяем что это назначение, которое можно отклонить
    if notification.event_type not in (
            NotificationEventType.ASSIGNED_RESPONSIBLE,
            NotificationEventType.ASSIGNED_USER,
    ):
        return None

    # Определяем тип привязки и тип ответного уведомления
    if notification.event_type == NotificationEventType.ASSIGNED_RESPONSIBLE:
        assignment_type = "responsible"
        decline_event = NotificationEventType.RESPONSIBLE_DECLINED
    else:
        assignment_type = "user"
        decline_event = NotificationEventType.USER_DECLINED

    # Находим активную привязку и закрываем её
    result = await db.execute(
        select(AssetAssignment).where(
            AssetAssignment.asset_id == notification.asset_id,
            AssetAssignment.employee_id == employee_id,
            AssetAssignment.assignment_type == assignment_type,
            AssetAssignment.end_date.is_(None),
            )
    )
    assignment = result.scalars().first()
    if assignment:
        from datetime import date
        assignment.end_date = date.today()

    # Помечаем уведомление как declined
    notification.status = NotificationStatus.DECLINED
    notification.responded_at = datetime.now()

    # Создаём ответное уведомление инициатору
    if notification.initiator_id:
        await create_notification(
            db=db,
            employee_id=notification.initiator_id,
            asset_id=notification.asset_id,
            event_type=decline_event,
            initiator_id=employee_id,
        )

    await db.commit()

    return {
        "notification_id": notification.notification_id,
        "declined": True,
    }


async def delete_notification(
        db: AsyncSession,
        notification_id: int,
        employee_id: str,
) -> bool:
    """Удалить уведомление"""
    notification = await get_notification_by_id(db, notification_id)
    if not notification or notification.employee_id != employee_id:
        return False

    await db.delete(notification)
    await db.commit()
    return True


async def delete_all_read(
        db: AsyncSession,
        employee_id: str,
) -> int:
    """Удалить все прочитанные уведомления"""
    result = await db.execute(
        select(Notification)
        .where(
            Notification.employee_id == employee_id,
            Notification.status == NotificationStatus.READ,
            )
    )
    notifications = result.scalars().all()

    count = 0
    for n in notifications:
        await db.delete(n)
        count += 1

    if count > 0:
        await db.commit()
    return count


async def get_unread_count(
        db: AsyncSession,
        employee_id: str,
) -> int:
    """Количество непрочитанных уведомлений"""
    result = await db.execute(
        select(func.count(Notification.notification_id))
        .where(
            Notification.employee_id == employee_id,
            Notification.status == NotificationStatus.UNREAD,
            )
    )
    return result.scalar_one()