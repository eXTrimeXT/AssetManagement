import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud_notifications import create_notification
from app.models.notifications.Notification import NotificationEventType

logger = logging.getLogger(__name__)


async def notify_assigned_responsible(
        db: AsyncSession,
        employee_id: str,
        asset_id: int,
        initiator_id: str,
) -> None:
    """
    Уведомить сотрудника о назначении его ответственным за актив.
    Вызывается когда админ привязывает сотрудника как responsible.
    """
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=NotificationEventType.ASSIGNED_RESPONSIBLE,
        initiator_id=initiator_id,
    )
    logger.info(
        f"[Notify] ASSIGNED_RESPONSIBLE: {employee_id} получил актив {asset_id} "
        f"от {initiator_id}"
    )


async def notify_assigned_user(
        db: AsyncSession,
        employee_id: str,
        asset_id: int,
        initiator_id: str,
) -> None:
    """
    Уведомить сотрудника о назначении его пользователем актива.
    Вызывается когда ответственный привязывает сотрудника как user.
    """
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=NotificationEventType.ASSIGNED_USER,
        initiator_id=initiator_id,
    )
    logger.info(
        f"[Notify] ASSIGNED_USER: {employee_id} получил актив {asset_id} "
        f"от {initiator_id}"
    )


async def notify_unassigned_responsible(
        db: AsyncSession,
        employee_id: str,
        asset_id: int,
        initiator_id: str,
) -> None:
    """
    Уведомить сотрудника о том, что его открепили как ответственного.
    """
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=NotificationEventType.UNASSIGNED_RESPONSIBLE,
        initiator_id=initiator_id,
    )
    logger.info(
        f"[Notify] UNASSIGNED_RESPONSIBLE: {employee_id} отвязан от актива {asset_id} "
        f"инициатором {initiator_id}"
    )


async def notify_unassigned_user(
        db: AsyncSession,
        employee_id: str,
        asset_id: int,
        initiator_id: str,
) -> None:
    """
    Уведомить сотрудника о том, что его открепили как пользователя.
    """
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=NotificationEventType.UNASSIGNED_USER,
        initiator_id=initiator_id,
    )
    logger.info(
        f"[Notify] UNASSIGNED_USER: {employee_id} отвязан от актива {asset_id} "
        f"инициатором {initiator_id}"
    )