from typing import Optional, Tuple, Sequence
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.notifications.Notification import Notification
from app.models.assets.Asset import Asset
from app.models.assets.AssetAssignment import AssetAssignment
from app.models.map_assets.AssetPosition import AssetPosition


def _asset_load_options():
    """Общие опции загрузки для Asset внутри Notification"""
    return [
        # Базовые relationship актива
        selectinload(Notification.asset).selectinload(Asset.asset_type),
        selectinload(Notification.asset).selectinload(Asset.asset_status),

        # Вместо Asset.location загружаем asset_positions с workshop
        # (computed_field location сам возьмёт данные из них)
        selectinload(Notification.asset)
        .selectinload(Asset.asset_positions)
        .selectinload(AssetPosition.workshop),

        # Для responsible_users и users (computed_field)
        selectinload(Notification.asset)
        .selectinload(Asset.assignments)
        .selectinload(AssetAssignment.employee),
    ]


async def get_notifications_by_employee(
        db: AsyncSession,
        employee_id: str,
        page: int = 1,
        page_size: int = 50,
        only_unchecked: bool = False,
) -> Tuple[Sequence[Notification], int]:
    """Получить уведомления сотрудника с пагинацией."""
    # Подсчёт
    count_query = (
        select(func.count(Notification.notification_id))
        .where(Notification.employee_id == employee_id)
    )
    if only_unchecked:
        count_query = count_query.where(Notification.notification_checked == False)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Данные с полной загрузкой связей Asset
    query = (
        select(Notification)
        .options(*_asset_load_options())
        .where(Notification.employee_id == employee_id)
    )
    if only_unchecked:
        query = query.where(Notification.notification_checked == False)

    query = query.order_by(Notification.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    notifications = result.scalars().all()

    return notifications, total


async def get_notification_by_id(
        db: AsyncSession,
        notification_id: int,
) -> Optional[Notification]:
    """Получить уведомление по ID."""
    result = await db.execute(
        select(Notification)
        .options(*_asset_load_options())
        .where(Notification.notification_id == notification_id)
    )
    return result.scalar_one_or_none()


async def mark_as_checked(
        db: AsyncSession,
        notification_id: int,
        employee_id: str,
) -> Optional[Notification]:
    """Отметить уведомление как проверенное (только если оно принадлежит сотруднику)."""
    notification = await get_notification_by_id(db, notification_id)
    if not notification or notification.employee_id != employee_id:
        return None

    notification.notification_checked = True
    await db.commit()
    await db.refresh(notification)
    return notification


async def mark_all_as_checked(
        db: AsyncSession,
        employee_id: str,
) -> int:
    """Отметить все уведомления сотрудника как проверенные. Возвращает количество обновлённых."""
    result = await db.execute(
        select(Notification)
        .where(
            Notification.employee_id == employee_id,
            Notification.notification_checked == False,
            )
    )
    notifications = result.scalars().all()

    count = 0
    for n in notifications:
        n.notification_checked = True
        count += 1

    if count > 0:
        await db.commit()
    return count


async def delete_notification(
        db: AsyncSession,
        notification_id: int,
        employee_id: str,
) -> bool:
    """Удалить уведомление (только если оно принадлежит сотруднику)."""
    notification = await get_notification_by_id(db, notification_id)
    if not notification or notification.employee_id != employee_id:
        return False

    await db.delete(notification)
    await db.commit()
    return True


async def delete_all_checked(
        db: AsyncSession,
        employee_id: str,
) -> int:
    """Удалить все проверенные уведомления сотрудника. Возвращает количество удалённых."""
    result = await db.execute(
        select(Notification)
        .where(
            Notification.employee_id == employee_id,
            Notification.notification_checked == True,
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


async def get_unchecked_count(
        db: AsyncSession,
        employee_id: str,
) -> int:
    """Количество непрочитанных уведомлений сотрудника."""
    result = await db.execute(
        select(func.count(Notification.notification_id))
        .where(
            Notification.employee_id == employee_id,
            Notification.notification_checked == False,
            )
    )
    return result.scalar_one()