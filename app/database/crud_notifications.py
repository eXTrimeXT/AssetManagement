import logging
from typing import Optional, Tuple, Sequence, Literal
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.notifications.Notification import (
    Notification, NotificationEventType, NotificationStatus
)
from app.models.assets.AssetAssignment import AssignmentTypeEnum

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

    return {
        "unchecked_count": unread_res.scalar_one(),
        "checked_count": read_res.scalar_one()
    }

async def get_notification_counts_grouped(
        db: AsyncSession,
        employee_id: str,
        direction: Literal["incoming", "outgoing", "all"] = "incoming",
        asset_id: Optional[int] = None,
        session_id: Optional[int] = None,
) -> dict:
    """Возвращает счётчики с общими суммами и группировкой по asset/session"""
    # Базовое условие по направлению
    if direction == "incoming":
        base_condition = and_(Notification.employee_id == employee_id, Notification.employee_deleted == False)
    elif direction == "outgoing":
        base_condition = and_(Notification.initiator_id == employee_id, Notification.initiator_deleted == False)
    else:  # "all"
        base_condition = or_(
            and_(Notification.employee_id == employee_id, Notification.employee_deleted == False),
            and_(Notification.initiator_id == employee_id, Notification.initiator_deleted == False)
        )

    # Считаем ОБЩИЕ суммы для верхнего уровня ответа
    total_query = select(
        func.count(Notification.notification_id).label("total"),
        func.count().filter(Notification.status == NotificationStatus.UNREAD).label("unchecked"),
        func.count().filter(Notification.status == NotificationStatus.READ).label("checked"),
    ).where(base_condition)

    total_res = await db.execute(total_query)
    total_row = total_res.one()

    # Логика группировки по asset (если нет фильтра по session)
    asset_counts = {}
    if session_id is None:
        asset_q = select(
            Notification.asset_id,
            func.count(Notification.notification_id).label("total"),
            func.count().filter(Notification.status == NotificationStatus.UNREAD).label("unchecked"),
            func.count().filter(Notification.status == NotificationStatus.READ).label("checked"),
        ).where(base_condition, Notification.asset_id.isnot(None))

        if asset_id is not None:
            asset_q = asset_q.where(Notification.asset_id == asset_id)

        asset_res = await db.execute(asset_q.group_by(Notification.asset_id))
        asset_counts = {str(row.asset_id): {
            "total": row.total,
            "unchecked_count": row.unchecked,
            "checked_count": row.checked,
        } for row in asset_res.all()}

    # Логика группировки по session (если нет фильтра по asset)
    session_counts = {}
    if asset_id is None:
        session_q = select(
            Notification.session_id,
            func.count(Notification.notification_id).label("total"),
            func.count().filter(Notification.status == NotificationStatus.UNREAD).label("unchecked"),
            func.count().filter(Notification.status == NotificationStatus.READ).label("checked"),
        ).where(base_condition, Notification.session_id.isnot(None))

        if session_id is not None:
            session_q = session_q.where(Notification.session_id == session_id)

        session_res = await db.execute(session_q.group_by(Notification.session_id))
        session_counts = {str(row.session_id): {
            "total": row.total,
            "unchecked_count": row.unchecked,
            "checked_count": row.checked,
        } for row in session_res.all()}

    # Формируем итоговый ответ с общими суммами на верхнем уровне
    result = {
        "total": total_row.total,
        "total_unchecked_count": total_row.unchecked,
        "total_checked_count": total_row.checked,
    }

    if session_id is None:
        result["asset"] = asset_counts
    if asset_id is None:
        result["session"] = session_counts

    return result

# Получение всех видов уведомлений
async def get_notifications_by_employee(
        db: AsyncSession,
        employee_id: str,
        page: int = 1,
        page_size: int = 50,
        only_unread: bool = False,
        asset_id: Optional[int] = None,
        session_id: Optional[int] = None,
        direction: Literal["incoming", "outgoing", "all"] = "all",
        notification_type: Literal["all", "asset", "session"] = "all",
) -> Tuple[Sequence[Notification], int]:

    # Базовое условие по направлению и мягкому удалению
    if direction == "incoming":
        condition = and_(
            Notification.employee_id == employee_id,
            Notification.employee_deleted == False
        )
    elif direction == "outgoing":
        condition = and_(
            Notification.initiator_id == employee_id,
            Notification.initiator_deleted == False
        )
    else:  # "all"
        condition = or_(
            and_(Notification.employee_id == employee_id, Notification.employee_deleted == False),
            and_(Notification.initiator_id == employee_id, Notification.initiator_deleted == False)
        )

    # Применяем фильтр по типу уведомления
    if notification_type == "asset":
        condition = and_(condition, Notification.asset_id.isnot(None))
    elif notification_type == "session":
        condition = and_(condition, Notification.session_id.isnot(None))

    # Дополнительные фильтры (если переданы конкретные ID)
    if asset_id is not None:
        condition = and_(condition, Notification.asset_id == asset_id)
    if session_id is not None:
        condition = and_(condition, Notification.session_id == session_id)
    if only_unread and direction != "outgoing":
        condition = and_(condition, Notification.status == NotificationStatus.UNREAD)

    # Подсчёт
    count_query = select(func.count(Notification.notification_id)).where(condition)
    total = (await db.execute(count_query)).scalar_one()

    # Получение данных
    query = (
        select(Notification)
        .options(
            selectinload(Notification.asset),
            selectinload(Notification.initiator),
            selectinload(Notification.recipient),
        )
        .where(condition)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

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
        current_user_id: str,
) -> bool:
    """
    Удаляет уведомление.
    - Если инициатор удаляет UNREAD уведомление -> жесткое удаление из БД.
    - В остальных случаях -> мягкое удаление (флаг deleted для конкретной роли).
    """
    notification = await get_notification_by_id(db, notification_id)
    if not notification:
        return False

    is_employee = (notification.employee_id == current_user_id)
    is_initiator = (notification.initiator_id == current_user_id)

    if not is_employee and not is_initiator:
        return False  # Пользователь не имеет права удалять это уведомление

    # Правило: Инициатор удаляет непрочитанное уведомление -> жесткое удаление
    if is_initiator and notification.status == NotificationStatus.UNREAD:
        await db.delete(notification)
        await db.commit()
        return True

    # В остальных случаях -> мягкое удаление
    if is_employee:
        notification.employee_deleted = True
    if is_initiator:
        notification.initiator_deleted = True

    await db.commit()
    return True


async def delete_all_read(db: AsyncSession, current_user_id: str) -> int:
    """Мягко удаляет все прочитанные уведомления для текущего пользователя"""

    # Находим все уведомления, которые видны пользователю и имеют статус READ
    visibility_condition = or_(
        and_(Notification.employee_id == current_user_id, Notification.employee_deleted == False),
        and_(Notification.initiator_id == current_user_id, Notification.initiator_deleted == False)
    )

    result = await db.execute(
        select(Notification).where(
            visibility_condition,
            Notification.status == NotificationStatus.READ
        )
    )
    notifications = result.scalars().all()

    count = 0
    for n in notifications:
        if n.employee_id == current_user_id:
            n.employee_deleted = True
        if n.initiator_id == current_user_id:
            n.initiator_deleted = True
        count += 1

    if count > 0:
        await db.commit()
    return count

# ============================================================
# БИЗНЕС-ЛОГИКА: ОБЁРТКИ ДЛЯ КОНКРЕТНЫХ ТИПОВ УВЕДОМЛЕНИЙ
# ============================================================
# Привязки/Отвязки
async def notify_assigned_user(db, employee_id, asset_id, initiator_id):
    """Уведомить о назначении пользователем."""
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=NotificationEventType.ASSIGNED_USER,
        initiator_id=initiator_id
    )

async def notify_assigned_responsible(db, employee_id, asset_id, initiator_id):
    """Уведомить о назначении ответственным."""
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=NotificationEventType.ASSIGNED_RESPONSIBLE,
        initiator_id=initiator_id
    )

async def notify_assigned_serving(db, employee_id, asset_id, initiator_id):
    """Уведомить о назначении обслуживающего."""
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=NotificationEventType.ASSIGNED_SERVING,
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

async def notify_unassigned_serving(db, employee_id, asset_id, initiator_id):
    """Уведомить об отвязке обслуживающего."""
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=NotificationEventType.UNASSIGNED_SERVING,
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


async def notify_assignment_declined(db, employee_id, asset_id, initiator_id, assignment_type) -> None:
    """
    Создает уведомление для assigned_by о том, что сотрудник отказался от актива.
    """
    # Определяем тип события в зависимости от типа привязки
    # event_type = "responsible_declined" if assignment_type == "responsible" else "user_declined"
    event_type = NotificationEventType.RESPONSIBLE_DECLINED if assignment_type == AssignmentTypeEnum.RESPONSIBLE else AssignmentTypeEnum.USER_DECLINED

    new_notification = Notification(
        employee_id=employee_id,      # Кому: тот, кто назначал (assigned_by)
        initiator_id=initiator_id,    # От кого: тот, кто отказался (current_user)
        asset_id=asset_id,
        event_type=event_type,
        status="unread",
    )

    db.add(new_notification)
    await db.commit()

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