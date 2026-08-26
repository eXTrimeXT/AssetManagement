import logging
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database.connection import async_session
from app.models.assets.Asset import Asset
from app.models.assets.AssetAssignment import AssetAssignment
from app.models.assets.AssetStatus import AssetStatus
from app.models.notifications.Notification import (
    Notification,
    NotificationEventType,
    NotificationStatus,
)

logger = logging.getLogger(__name__)

SERVICE_REQUIRED_STATUS = "Требует проверки"


async def get_or_create_service_status(session) -> AssetStatus:
    """Получить статус 'Требует проверки' или создать его."""
    result = await session.execute(
        select(AssetStatus).where(AssetStatus.status == SERVICE_REQUIRED_STATUS)
    )
    status_obj = result.scalars().first()

    if status_obj:
        logger.debug(f"Статус '{SERVICE_REQUIRED_STATUS}' найден: id={status_obj.id}")
        return status_obj

    new_status = AssetStatus(status=SERVICE_REQUIRED_STATUS)
    session.add(new_status)
    await session.flush()
    logger.info(f"Создан статус '{SERVICE_REQUIRED_STATUS}': id={new_status.id}")
    return new_status


def _calculate_service_period(asset: Asset) -> int:
    """
    Определяет период обслуживания в днях.
    Возвращает 0 если актив нужно пропустить.
    """
    if asset.every_week_check:
        return 7
    elif asset.service_period is not None and asset.service_period > 0:
        return asset.service_period
    return 0


async def check_service_assets():
    """
    Планировщик проверки оборудования.

    Логика:
    - every_week_check=True → период 7 дней
    - every_week_check=False, service_period IS NULL → пропуск
    - every_week_check=False, service_period > 0 → период = service_period
    """
    logger.info("🔧 Запуск задачи проверки активов...")
    today = date.today()

    async with async_session() as session:
        service_status = await get_or_create_service_status(session)

        # Получаем активы с наступившим сроком обслуживания
        result = await session.execute(
            select(Asset)
            .options(
                selectinload(Asset.asset_status),
                selectinload(Asset.assignments).options(
                    selectinload(AssetAssignment.employee)
                ),
            )
            .where(
                Asset.next_service <= today,
                Asset.next_service.isnot(None),
                (Asset.every_week_check == True) | (
                        (Asset.every_week_check == False) &
                        (Asset.service_period.isnot(None))
                )
            )
        )
        assets = result.scalars().all()

        if not assets:
            logger.info("Нет активов, требующих обслуживания")
            return

        logger.info(f"📋 Найдено активов: {len(assets)}")

        notifications_created = 0
        assets_updated = 0

        for asset in assets:
            period = _calculate_service_period(asset)
            if period == 0:
                logger.debug(f"  ⊘ Актив {asset.asset_id}: пропущен (нет периода)")
                continue

            # Находим активных ответственных
            responsible_users = [
                a for a in asset.assignments
                if a.assignment_type == "responsible" and a.end_date is None
            ]

            if not responsible_users:
                logger.debug(f"  ⊘ Актив {asset.asset_id}: нет ответственных")
                continue

            # Создаём уведомления для каждого ответственного
            for assignment in responsible_users:
                notification = Notification(
                    employee_id=assignment.employee_id,
                    asset_id=asset.asset_id,
                    event_type=NotificationEventType.SERVICE_ACTION,
                    initiator_id=None,  # Системное уведомление
                    status=NotificationStatus.UNREAD,
                )
                session.add(notification)
                notifications_created += 1

            # Изменяем статус
            old_status = asset.asset_status.status if asset.asset_status else None
            asset.asset_status_id = service_status.id

            # Сдвигаем next_service
            asset.next_service = today + timedelta(days=period)
            assets_updated += 1

            logger.info(
                f"  ✓ Актив {asset.asset_id} ({asset.name}): "
                f"статус '{old_status}' → '{SERVICE_REQUIRED_STATUS}', "
                f"next_service → {asset.next_service}, "
                f"уведомлений: {len(responsible_users)}"
            )

        # Сохраняем изменения
        if notifications_created > 0 or assets_updated > 0:
            await session.commit()
            logger.info(
                f"Завершено: {notifications_created} уведомлений, "
                f"{assets_updated} активов обновлено"
            )
        else:
            logger.info("Нет изменений для сохранения")