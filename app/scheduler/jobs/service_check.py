import logging
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database.connection import async_session
from app.models.assets.Asset import Asset
from app.models.assets.AssetAssignment import AssetAssignment
from app.models.assets.AssetStatus import AssetStatus
from app.models.notifications.Notification import Notification

logger = logging.getLogger(__name__)

SERVICE_REQUIRED_STATUS = "Требует проверки"


async def get_or_create_service_status(session) -> AssetStatus:
    """Получить статус 'Требует проверки' или создать его."""
    result = await session.execute(
        select(AssetStatus).where(AssetStatus.status == SERVICE_REQUIRED_STATUS)
    )
    status_obj = result.scalars().first()

    if status_obj:
        logger.info(f"Статус '{SERVICE_REQUIRED_STATUS}' найден: id={status_obj.id}")
        return status_obj

    new_status = AssetStatus(status=SERVICE_REQUIRED_STATUS)
    session.add(new_status)
    await session.flush()
    logger.info(f"Создан статус '{SERVICE_REQUIRED_STATUS}': id={new_status.id}")
    return new_status


async def check_service_assets():
    """Проверка активов, требующих обслуживания."""
    logger.info("Запуск задачи проверки активов...")
    today = date.today()

    async with async_session() as session:
        service_status = await get_or_create_service_status(session)

        # Подгружаем asset_status, чтобы получить старое название статуса
        result = await session.execute(
            select(Asset)
            .options(
                selectinload(Asset.asset_status),
                selectinload(Asset.assignments).options(
                    selectinload(AssetAssignment.employee)
                ),
            )
            .where(
                Asset.every_week_check == True,
                Asset.next_service <= today,
                Asset.next_service.isnot(None),
                )
        )
        assets = result.scalars().all()

        logger.info(f"Найдено активов, требующих обслуживания (next_service <= {today}): {len(assets)}")

        total_notifications_created = 0
        total_assets_updated = 0

        for asset in assets:
            logger.info(
                f"Обработка актива: id={asset.asset_id}, name={asset.name}, "
                f"next_service={asset.next_service}, service_period={asset.service_period}"
            )

            # Определяем старое название статуса
            old_status_name = asset.asset_status.status if asset.asset_status else None
            old_status_id = asset.asset_status_id

            responsible = [
                a for a in asset.assignments
                if a.assignment_type == "responsible" and a.end_date is None
            ]

            if not responsible:
                logger.info(f"  Актив {asset.asset_id}: нет активных ответственных, пропускаем")
                continue

            # Создаём уведомления
            for assignment in responsible:
                notification = Notification(
                    employee_id=assignment.employee_id,
                    asset_id=asset.asset_id,
                    notification_checked=False,
                )
                session.add(notification)
                logger.info(
                    f"  [+] Уведомление: employee={assignment.employee_id}, asset={asset.asset_id}"
                )
                total_notifications_created += 1

            # Изменяем статус
            asset.asset_status_id = service_status.id
            logger.info(
                f"  [+] Статус изменён: '{old_status_name}' (id={old_status_id}) -> "
                f"'{SERVICE_REQUIRED_STATUS}' (id={service_status.id})"
            )

            # Сдвигаем next_service
            period = asset.service_period if asset.service_period and asset.service_period > 0 else 7
            asset.next_service = today + timedelta(days=period)
            total_assets_updated += 1
            logger.info(f"  [+] next_service сдвинут на {period} дней: {asset.next_service}")

        if total_notifications_created > 0 or total_assets_updated > 0:
            await session.commit()
            logger.info(
                f"Сохранено: {total_notifications_created} уведомлений, "
                f"{total_assets_updated} активов обновлено"
            )
        else:
            logger.info("Нет активов, требующих обслуживания")

    logger.info("Задача проверки активов завершена.")