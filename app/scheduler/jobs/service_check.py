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

SERVICE_REQUIRED_STATUS = "На обслуживании"


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
    """
    Проверка активов, требующих обслуживания.

    Логика:
    - every_week_check = True  → прибавляем 7 дней
    - every_week_check = False и service_period IS NULL → пропускаем
    - every_week_check = False и service_period IS NOT NULL → прибавляем service_period дней
    """
    logger.info("Запуск задачи проверки активов...")
    today = date.today()

    async with async_session() as session:
        service_status = await get_or_create_service_status(session)

        # Подгружаем asset_status и assignments
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
                # Либо every_week_check = True
                # Либо (every_week_check = False И service_period IS NOT NULL)
                (Asset.every_week_check == True) | (
                        (Asset.every_week_check == False) &
                        (Asset.service_period.isnot(None))
                )
            )
        )
        assets = result.scalars().all()

        logger.info(f"Найдено активов, требующих обслуживания (next_service <= {today}): {len(assets)}")

        total_notifications_created = 0
        total_assets_updated = 0

        for asset in assets:
            # Определяем period в зависимости от логики
            if asset.every_week_check:
                period = 7
            elif asset.service_period is not None and asset.service_period > 0:
                period = asset.service_period
            else:
                # service_period IS NULL или <= 0 — пропускаем (на всякий случай)
                logger.info(f"  Актив {asset.asset_id}: пропущен (нет периода обслуживания)")
                continue

            logger.info(
                f"Обработка актива: id={asset.asset_id}, name={asset.name}, "
                f"every_week_check={asset.every_week_check}, service_period={asset.service_period}, "
                f"next_service={asset.next_service}, period={period}"
            )

            # Определяем старое название статуса
            old_status_name = asset.asset_status.status if asset.asset_status else None
            old_status_id = asset.asset_status_id

            # Находим активных ответственных
            responsible = [
                a for a in asset.assignments
                if a.assignment_type == "responsible" and a.end_date is None
            ]

            if not responsible:
                logger.info(f"  Актив {asset.asset_id}: нет активных ответственных, пропускаем")
                continue

            # Создаём уведомления для каждого ответственного
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

            # Изменяем статус на "Требует проверки"
            asset.asset_status_id = service_status.id
            logger.info(
                f"  [+] Статус изменён: '{old_status_name}' (id={old_status_id}) -> "
                f"'{SERVICE_REQUIRED_STATUS}' (id={service_status.id})"
            )

            # Сдвигаем next_service на period дней
            asset.next_service = today + timedelta(days=period)
            total_assets_updated += 1
            logger.info(f"  [+] next_service сдвинут на {period} дней: {asset.next_service}")

        # Сохраняем все изменения
        if total_notifications_created > 0 or total_assets_updated > 0:
            await session.commit()
            logger.info(
                f"Сохранено: {total_notifications_created} уведомлений, "
                f"{total_assets_updated} активов обновлено"
            )
        else:
            logger.info("Нет активов, требующих обслуживания")

    logger.info("Задача проверки активов завершена.")