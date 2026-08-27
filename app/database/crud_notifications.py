import logging
from typing import Optional, Tuple, Sequence, Literal
from datetime import datetime
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.notifications.Notification import (
    Notification, NotificationEventType, NotificationStatus
)
from app.models.assets.AssetAssignment import AssetAssignment

logger = logging.getLogger(__name__)


# ============================================================
# БАЗОВЫЕ CRUD-ОПЕРАЦИИ
# ============================================================
async def create_notification(
        db: AsyncSession,
        employee_id: str,
        asset_id: Optional[int] = None,
        session_id: Optional[int] = None,
        event_type: str = None,
        initiator_id: Optional[str] = None,
) -> Notification:
    """ Создать уведомление """
    notification = Notification(
        employee_id=employee_id,
        asset_id=asset_id,
        session_id=session_id,
        event_type=event_type,
        initiator_id=initiator_id,
        status=NotificationStatus.UNREAD,
    )
    db.add(notification)
    await db.flush()

    logger.info(
        f"[Notify] {event_type}: employee={employee_id}, "
        f"asset={asset_id}, session_id={session_id}, initiator={initiator_id}"
    )
    return notification

async def get_notification_counts(db: AsyncSession, employee_id: str) -> dict:
    """Возвращает количество входящих уведомлений по статусам"""
    base_incoming = Notification.employee_id == employee_id

    unread_res = await db.execute(select(func.count()).where(base_incoming, Notification.status == NotificationStatus.UNREAD))
    read_res = await db.execute(select(func.count()).where(base_incoming, Notification.status == NotificationStatus.READ))
    declined_res = await db.execute(select(func.count()).where(base_incoming, Notification.status == NotificationStatus.DECLINED))

    return {
        "unchecked_count": unread_res.scalar_one(),
        "checked_count": read_res.scalar_one(),
        "declined_count": declined_res.scalar_one(),
    }

# ФУНКЦИЯ ПОЛУЧЕНИЯ СПИСКА
async def get_notifications_by_employee(
        db: AsyncSession,
        employee_id: str,
        page: int = 1,
        page_size: int = 50,
        only_unread: bool = False,
        asset_id: Optional[int] = None,
        direction: Literal["incoming", "outgoing", "all"] = "incoming",
) -> Tuple[Sequence[Notification], int]:

    # 1. Жёсткая логика фильтрации по направлению
    if direction == "incoming":
        condition = Notification.employee_id == employee_id
    elif direction == "outgoing":
        condition = Notification.initiator_id == employee_id
    else: # "all"
        condition = or_(Notification.employee_id == employee_id, Notification.initiator_id == employee_id)

    # 2. Подсчёт
    count_query = select(func.count(Notification.notification_id)).where(condition)
    if only_unread and direction != "outgoing":
        count_query = count_query.where(Notification.status == NotificationStatus.UNREAD)
    if asset_id is not None:
        count_query = count_query.where(Notification.asset_id == asset_id)

    total = (await db.execute(count_query)).scalar_one()

    # 3. Получение данных (с selectinload для предотвращения MissingGreenlet)
    query = (
        select(Notification)
        .options(
            selectinload(Notification.asset),
            selectinload(Notification.initiator),
            selectinload(Notification.recipient),
        )
        .where(condition)
    )

    if only_unread and direction != "outgoing":
        query = query.where(Notification.status == NotificationStatus.UNREAD)
    if asset_id is not None:
        query = query.where(Notification.asset_id == asset_id)

    query = query.order_by(Notification.created_at.desc()).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    return result.scalars().all(), total

async def get_notification_by_id(db: AsyncSession, notification_id: int) -> Optional[Notification]:
    result = await db.execute(
        select(Notification)
        .options(
            selectinload(Notification.asset),
            selectinload(Notification.initiator),
            selectinload(Notification.recipient),
        )
        .where(Notification.notification_id == notification_id)
    )
    return result.scalar_one_or_none()

async def get_unread_count(db: AsyncSession, employee_id: str) -> int:
    result = await db.execute(
        select(func.count(Notification.notification_id))
        .where(Notification.employee_id == employee_id, Notification.status == NotificationStatus.UNREAD)
    )
    return result.scalar_one()

async def get_notifications_grouped_by_asset(
        db: AsyncSession,
        employee_id: str,
) -> dict:
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

    grouped = {}
    for n in notifications:
        if n.asset_id not in grouped:
            grouped[n.asset_id] = []
        grouped[n.asset_id].append(n)
    return grouped


async def mark_as_read(
        db: AsyncSession,
        notification_id: int,
        employee_id: str,
) -> Optional[Notification]:
    notification = await get_notification_by_id(db, notification_id)
    if not notification or notification.employee_id != employee_id:
        return None
    notification.status = NotificationStatus.READ
    await db.commit()
    await db.refresh(notification)
    return notification


async def mark_all_as_read(db: AsyncSession, employee_id: str) -> int:
    result = await db.execute(
        select(Notification).where(
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


async def delete_notification(
        db: AsyncSession,
        notification_id: int,
        employee_id: str,
) -> bool:
    notification = await get_notification_by_id(db, notification_id)
    if not notification or notification.employee_id != employee_id:
        return False
    await db.delete(notification)
    await db.commit()
    return True


async def delete_all_read(db: AsyncSession, employee_id: str) -> int:
    result = await db.execute(
        select(Notification).where(
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

    if notification.event_type not in (
            NotificationEventType.ASSIGNED_RESPONSIBLE,
            NotificationEventType.ASSIGNED_USER,
    ):
        return None

    if notification.event_type == NotificationEventType.ASSIGNED_RESPONSIBLE:
        assignment_type = "responsible"
        decline_event = NotificationEventType.RESPONSIBLE_DECLINED
    else:
        assignment_type = "user"
        decline_event = NotificationEventType.USER_DECLINED

    # Закрываем привязку
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


# ============================================================
# БИЗНЕС-ЛОГИКА: ОБЁРТКИ ДЛЯ КОНКРЕТНЫХ ТИПОВ УВЕДОМЛЕНИЙ
# ============================================================
# Привязки/Отвязки
async def notify_assigned_responsible(db, employee_id, asset_id, initiator_id):
    """Уведомить о назначении ответственным."""
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=NotificationEventType.ASSIGNED_RESPONSIBLE,
        initiator_id=initiator_id
    )

async def notify_assigned_user(db, employee_id, asset_id, initiator_id):
    """Уведомить о назначении пользователем."""
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=NotificationEventType.ASSIGNED_USER,
        initiator_id=initiator_id
    )

async def notify_unassigned_responsible(db, employee_id, asset_id, initiator_id):
    """Уведомить об отвязке ответственного."""
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=NotificationEventType.UNASSIGNED_RESPONSIBLE,
        initiator_id=initiator_id
    )

async def notify_unassigned_user(db, employee_id, asset_id, initiator_id):
    """Уведомить об отвязке пользователя."""
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=NotificationEventType.UNASSIGNED_USER,
        initiator_id=initiator_id
    )

# Списания
async def notify_write_off_requested(db, employee_id, asset_id, initiator_id):
    """Уведомить о создании заявки на списание."""
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=NotificationEventType.WRITE_OFF_REQUESTED,
        initiator_id=initiator_id
    )

async def notify_write_off_approved(db, employee_id, asset_id, initiator_id):
    """Уведомить об утверждении списания."""
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=NotificationEventType.WRITE_OFF_APPROVED,
        initiator_id=initiator_id
    )

async def notify_write_off_rejected(db, employee_id, asset_id, initiator_id):
    """Уведомить об отклонении списания."""
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=NotificationEventType.WRITE_OFF_REJECTED,
        initiator_id=initiator_id
    )


# Инвентаризация
async def notify_inventory_started(db: AsyncSession, employee_id: str, session_id: int, initiator_id: str):
    """Уведомить сотрудника о начале инвентаризации сессии (ОДНО уведомление на сессию)"""
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=None, # Привязка идет к сессии, а не к конкретному активу
        session_id=session_id,
        event_type=NotificationEventType.INVENTORY_STARTED,
        initiator_id=initiator_id,
    )

async def notify_inventory_discrepancy(db: AsyncSession, employee_id: str, asset_id: int, session_id: int, initiator_id: str):
    """Уведомить о расхождении по КОНКРЕТНОМУ активу в сессии"""
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        session_id=session_id,
        event_type=NotificationEventType.INVENTORY_DISCREPANCY,
        initiator_id=initiator_id,
    )

async def notify_inventory_completed(db: AsyncSession, employee_id: str, session_id: int, initiator_id: str):
    """Уведомить о завершении сессии инвентаризации"""
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=None,
        session_id=session_id,
        event_type=NotificationEventType.INVENTORY_COMPLETED,
        initiator_id=initiator_id,
    )