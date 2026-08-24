import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud_notifications import create_notification
from app.models.notifications.Notification import NotificationEventType

logger = logging.getLogger(__name__)


async def _send_notification(
        db: AsyncSession,
        event_type: str,
        employee_id: str,
        asset_id: int,
        initiator_id: Optional[str],
) -> None:
    """
    Универсальная функция отправки уведомления.
    Внутренний helper для избежания дублирования кода.
    """
    await create_notification(
        db=db,
        employee_id=employee_id,
        asset_id=asset_id,
        event_type=event_type,
        initiator_id=initiator_id,
    )
    logger.info(
        f"[Notify] {event_type}: employee={employee_id}, "
        f"asset={asset_id}, initiator={initiator_id}"
    )


async def notify_assigned_responsible(
        db: AsyncSession,
        employee_id: str,
        asset_id: int,
        initiator_id: str,
) -> None:
    """Уведомить сотрудника о назначении ответственным за актив."""
    await _send_notification(
        db=db,
        event_type=NotificationEventType.ASSIGNED_RESPONSIBLE,
        employee_id=employee_id,
        asset_id=asset_id,
        initiator_id=initiator_id,
    )


async def notify_assigned_user(
        db: AsyncSession,
        employee_id: str,
        asset_id: int,
        initiator_id: str,
) -> None:
    """Уведомить сотрудника о назначении пользователем актива."""
    await _send_notification(
        db=db,
        event_type=NotificationEventType.ASSIGNED_USER,
        employee_id=employee_id,
        asset_id=asset_id,
        initiator_id=initiator_id,
    )


async def notify_unassigned_responsible(
        db: AsyncSession,
        employee_id: str,
        asset_id: int,
        initiator_id: str,
) -> None:
    """Уведомить сотрудника об отвязке от актива как ответственного."""
    await _send_notification(
        db=db,
        event_type=NotificationEventType.UNASSIGNED_RESPONSIBLE,
        employee_id=employee_id,
        asset_id=asset_id,
        initiator_id=initiator_id,
    )


async def notify_unassigned_user(
        db: AsyncSession,
        employee_id: str,
        asset_id: int,
        initiator_id: str,
) -> None:
    """Уведомить сотрудника об отвязке от актива как пользователя."""
    await _send_notification(
        db=db,
        event_type=NotificationEventType.UNASSIGNED_USER,
        employee_id=employee_id,
        asset_id=asset_id,
        initiator_id=initiator_id,
    )


""" Списание """
async def notify_write_off_requested(
        db: AsyncSession,
        employee_id: str,
        asset_id: int,
        initiator_id: str,
) -> None:
    """Уведомить о создании заявки на списание."""
    await _send_notification(
        db=db,
        event_type=NotificationEventType.WRITE_OFF_REQUESTED,
        employee_id=employee_id,
        asset_id=asset_id,
        initiator_id=initiator_id,
    )


async def notify_write_off_approved(
        db: AsyncSession,
        employee_id: str,
        asset_id: int,
        initiator_id: str,
) -> None:
    """Уведомить об утверждении заявки на списание."""
    await _send_notification(
        db=db,
        event_type=NotificationEventType.WRITE_OFF_APPROVED,
        employee_id=employee_id,
        asset_id=asset_id,
        initiator_id=initiator_id,
    )


async def notify_write_off_rejected(
        db: AsyncSession,
        employee_id: str,
        asset_id: int,
        initiator_id: str,
) -> None:
    """Уведомить об отклонении заявки на списание."""
    await _send_notification(
        db=db,
        event_type=NotificationEventType.WRITE_OFF_REJECTED,
        employee_id=employee_id,
        asset_id=asset_id,
        initiator_id=initiator_id,
    )