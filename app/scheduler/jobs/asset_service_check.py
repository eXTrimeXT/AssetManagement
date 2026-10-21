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

# === ДОБАВЛЕНЫ ИМПОРТЫ ДЛЯ СОЗДАНИЯ ЗАЯВКИ НА ПОДТВЕРЖДЕНИЕ ===
from app.models.assets.AssetConfirmation import AssetConfirmation, AssetConfirmationStatus

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
            logger.info("Нет активов, требующих обслуживания")
            return

        logger.warning(f"Найдено активов требующих обслуживания: {len(assets)}")

        notifications_created = 0
        assets_updated = 0

        for asset in assets:
            period = _calculate_service_period(asset)
            if period == 0:
                logger.warning(f"Актив {asset.asset_id}: пропущен (нет периода)")
                continue

            # Находим активных ответственных за обслуживание
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
            logger.info("Нет изменений для сохранения")


async def check_have_assets():
    """
    Планировщик проверки оборудования.
    Также создает заявку на подтверждение наличия (AssetConfirmation).
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
            logger.info("Нет активов, требующих проверки")
            return

        logger.warning(f"Найдено активов требующих проверку: {len(assets)}")

        notifications_created = 0
        assets_updated = 0
        confirmations_created = 0  # <-- НОВАЯ ПЕРЕМЕННАЯ ДЛЯ ПОДСЧЕТА ЗАЯВОК

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

            for assignment in users:
                # 1. ЗАЩИТА ОТ ДУБЛИКАТОВ: Проверяем, нет ли уже активной заявки
                existing_confirmation = await session.execute(
                    select(AssetConfirmation).where(
                        AssetConfirmation.asset_id == asset.asset_id,
                        AssetConfirmation.employee_id == assignment.employee_id,
                        AssetConfirmation.status == AssetConfirmationStatus.PENDING
                    )
                )
                if existing_confirmation.scalar_one_or_none():
                    logger.debug(f"Заявка на подтверждение для актива {asset.asset_id} и сотрудника {assignment.employee_id} уже существует.")
                    continue

                # 2. Создаём уведомление
                notification = Notification(
                    employee_id=assignment.employee_id,
                    asset_id=asset.asset_id,
                    event_type=NotificationEventType.CHECK_REQUIRE,
                    initiator_id=None,  # Системное уведомление
                    status=NotificationStatus.UNREAD,
                )
                session.add(notification)
                notifications_created += 1

                # 3. Создаём заявку на подтверждение наличия (AssetConfirmation)
                confirmation = AssetConfirmation(
                    asset_id=asset.asset_id,
                    employee_id=assignment.employee_id,
                    requested_by=None,  # None означает, что заявку инициировала система (планировщик)
                    status=AssetConfirmationStatus.PENDING,
                    comment="Автоматическая заявка по графику проверки"
                )
                session.add(confirmation)
                confirmations_created += 1

            # Изменяем статус актива (делаем это один раз на актив)
            old_status = asset.asset_status.status if asset.asset_status else None
            asset.asset_status_id = status.id

            # Сдвигаем next_check
            asset.next_check = today + timedelta(days=period)
            assets_updated += 1

            logger.info(
                f"Актив {asset.asset_id} ({asset.name}): "
                f"статус '{old_status}' → '{CHECK_REQUIRED_STATUS}', "
                f"next_check → {asset.next_check}"
            )

        # Сохраняем изменения
        if notifications_created > 0 or assets_updated > 0:
            await session.commit()
            logger.info(
                f"Завершено: {notifications_created} уведомлений, "
                f"{confirmations_created} заявок на подтверждение создано, "
                f"{assets_updated} активов обновлено"
            )
        else:
            logger.info("Нет изменений для сохранения")