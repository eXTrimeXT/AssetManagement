import logging
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database.connection import async_session
from app.models.assets.AssetAssignment import AssetAssignment
from app.models.notifications.Notification import (
    Notification,
    NotificationEventType,
    NotificationStatus,
)
from app.models.assets import Asset
from app.database.assets.crud_asset_status import get_or_create_status

logger = logging.getLogger(__name__)

SERVICE_REQUIRED_STATUS = "Требует обслуживания"
CHECK_REQUIRED_STATUS = "Требует проверки"

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

def _calculate_check_period(asset: Asset) -> int:
    """
    Определяет период проверки в днях.
    Возвращает 0 если актив нужно пропустить.
    """
    if asset.check_period is not None and asset.check_period > 0:
        return asset.check_period
    return 0

async def check_service_assets():
    """
    Планировщик обслуживания оборудования.

    Логика:
    - every_week_check=False, service_period IS NULL → пропуск
    - every_week_check=False, service_period > 0 → период = service_period
    """
    today = date.today()
    logger.info(f"Запуск задачи обслуживания активов... {today=}")

    async with async_session() as session:
        service_status = await get_or_create_status(session=session, status=SERVICE_REQUIRED_STATUS)

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
                Asset.next_service == today,
                Asset.next_service.isnot(None),
                (Asset.every_week_check == True) | (
                        (Asset.every_week_check == False) &
                        (Asset.service_period.isnot(None))
                )
            )
        )
        assets = result.scalars().all()

        if not assets:
            logger.warning("Нет активов, требующих обслуживания")
            return

        logger.warning(f"Найдено активов требующих обслуживания: {len(assets)}")

        notifications_created = 0
        assets_updated = 0

        for asset in assets:
            period = _calculate_service_period(asset)
            if period == 0:
                logger.warning(f"Актив {asset.asset_id}: пропущен (нет периода)")
                continue

            # Находим активных ответственных
            serving_users = [
                a for a in asset.assignments
                if a.assignment_type == "serving" and a.end_date is None
            ]

            if not serving_users:
                logger.warning(f"Актив {asset.asset_id}: обслуживающие отсутствуют!")
                continue

            # Создаём уведомления для каждого ответственного
            for assignment in serving_users:
                notification = Notification(
                    employee_id=assignment.employee_id,
                    asset_id=asset.asset_id,
                    event_type=NotificationEventType.SERVICE_REQUIRE,
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
                f"Актив {asset.asset_id} ({asset.name}): "
                f"статус '{old_status}' → '{SERVICE_REQUIRED_STATUS}', "
                f"next_service → {asset.next_service}, "
                f"уведомлений: {len(serving_users)}"
            )

        # Сохраняем изменения
        if notifications_created > 0 or assets_updated > 0:
            await session.commit()
            logger.info(
                f"Завершено: {notifications_created} уведомлений, "
                f"{assets_updated} активов обновлено"
            )
        else:
            pass
            logger.info("Нет изменений для сохранения")


async def check_have_assets():
    """
    Планировщик проверки оборудования.
    """

    today = date.today()
    logger.info(f"Запуск задачи проверки активов... {today=}")

    async with async_session() as session:
        status = await get_or_create_status(session=session, status=CHECK_REQUIRED_STATUS)

        # Получаем активы с наступившим сроком проверки
        result = await session.execute(
            select(Asset)
            .options(
                selectinload(Asset.asset_status),
                selectinload(Asset.assignments).options(
                    selectinload(AssetAssignment.employee)
                ),
            )
            .where(
                Asset.next_check == today,
                Asset.next_check.isnot(None),
            )
        )
        assets = result.scalars().all()

        if not assets:
            logger.warning("Нет активов, требующих проверки")
            return

        logger.warning(f"Найдено активов требующих проверку: {len(assets)}")

        notifications_created = 0
        assets_updated = 0

        for asset in assets:
            period = _calculate_check_period(asset)
            if period == 0:
                logger.warning(f"Актив {asset.asset_id}: пропущен (нет периода)")
                continue

            # Находим активных владельцев
            users = [
                a for a in asset.assignments
                if a.assignment_type == "user" and a.end_date is None
            ]

            if not users:
                logger.warning(f"Актив {asset.asset_id}: нет проверяющих!")
                continue

            # Создаём уведомления для каждого ответственного
            for assignment in users:
                notification = Notification(
                    employee_id=assignment.employee_id,
                    asset_id=asset.asset_id,
                    event_type=NotificationEventType.CHECK_REQUIRE,
                    initiator_id=None,  # Системное уведомление
                    status=NotificationStatus.UNREAD,
                )
                session.add(notification)
                notifications_created += 1

            # Изменяем статус
            old_status = asset.asset_status.status if asset.asset_status else None
            asset.asset_status_id = status.id

            # Сдвигаем next_check
            asset.next_check = today + timedelta(days=period)
            assets_updated += 1

            logger.info(
                f"Актив {asset.asset_id} ({asset.name}): "
                f"статус '{old_status}' → '{CHECK_REQUIRED_STATUS}', "
                f"next_check → {asset.next_check}, "
                f"уведомлений: {len(users)}"
            )

        # Сохраняем изменения
        if notifications_created > 0 or assets_updated > 0:
            await session.commit()
            logger.info(
                f"Завершено: {notifications_created} уведомлений, "
                f"{assets_updated} активов обновлено"
            )
        else:
            pass
            logger.info("Нет изменений для сохранения")