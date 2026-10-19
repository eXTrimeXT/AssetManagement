import logging
from sqlalchemy import update, select, func, distinct
from app.database.connection import async_session
from app.models.inventorization.Inventorization import InventorizationSession, InventorizationStatus, \
    InventorizationItem
from app.database.crud_notifications import notify_inventory_started
from app.models.assets.AssetAssignment import AssetAssignment

logger = logging.getLogger(__name__)

async def check_inventorization_dates():
    """
    Периодическая задача для автоматического изменения статуса сессий инвентаризации.
    ЗАЩИТНАЯ ПРОВЕРКА: Использует func.now() для сравнения времени НА СТОРОНЕ БД.
    """
    logger.info("[INVENTORY SCHEDULER] Запуск проверки дат инвентаризации...")
    try:
        async with async_session() as db:
            updated_start = 0
            updated_end = 0

            # 1. Переводим сессии в IN_PROGRESS, если наступила дата начала
            stmt_start = (
                update(InventorizationSession)
                .where(
                    InventorizationSession.status == InventorizationStatus.PENDING,
                    InventorizationSession.start_date.isnot(None),
                    InventorizationSession.start_date <= func.now()
                )
                .values(status=InventorizationStatus.IN_PROGRESS)
            )
            result_start = await db.execute(stmt_start)
            updated_start = result_start.rowcount

            # 2. Переводим сессии в COMPLETED, если наступила дата окончания
            stmt_end = (
                update(InventorizationSession)
                .where(
                    InventorizationSession.status == InventorizationStatus.IN_PROGRESS,
                    InventorizationSession.end_date.isnot(None),
                    InventorizationSession.end_date <= func.now()
                )
                .values(status=InventorizationStatus.COMPLETED)
            )
            result_end = await db.execute(stmt_end)
            updated_end = result_end.rowcount

            if updated_start > 0 or updated_end > 0:
                await db.commit()
                logger.info(
                    f"[INVENTORY SCHEDULER] Автоматически обновлены статусы: "
                    f"начато={updated_start}, завершено={updated_end}"
                )
            else:
                logger.debug("[INVENTORY SCHEDULER] Нет сессий, требующих изменения статуса.")

    except Exception as e:
        logger.error(f"[INVENTORY SCHEDULER] Ошибка при проверке дат инвентаризации: {e}", exc_info=True)

async def start_inventory_session_job(session_id: int):
    """
    Задача для автоматического запуска сессии инвентаризации в указанное время.
    Вызывается APScheduler'ом через DateTrigger или периодически.
    """
    logger.info(f"[INVENTORY SCHEDULER] Запуск задачи start_inventory_session_job для session_id={session_id}")
    try:
        async with async_session() as db:
            # 1. Проверяем, что сессия существует и все еще в статусе PENDING
            stmt = select(InventorizationSession).where(
                InventorizationSession.session_id == session_id,
                InventorizationSession.status == InventorizationStatus.PENDING
            )
            result = await db.execute(stmt)
            session = result.scalar_one_or_none()

            if not session:
                logger.warning(f"[INVENTORY SCHEDULER] Сессия {session_id} не найдена или уже не в статусе PENDING")
                return

            # 2. Меняем статус на IN_PROGRESS
            session.status = InventorizationStatus.IN_PROGRESS

            # 3. === НОВАЯ ЛОГИКА: ОТПРАВКА УВЕДОМЛЕНИЙ О НАЧАЛЕ ===
            # Находим все asset_id для этой сессии (игнорируем виртуальные SAP, у которых asset_id is None)
            items_stmt = select(InventorizationItem.asset_id).where(
                InventorizationItem.session_id == session_id,
                InventorizationItem.asset_id.isnot(None)
            )
            items_result = await db.execute(items_stmt)
            asset_ids = [row[0] for row in items_result.all()]

            if asset_ids:
                # Находим уникальных ответственных сотрудников для этих активов
                employees_stmt = select(distinct(AssetAssignment.employee_id)).where(
                    AssetAssignment.asset_id.in_(asset_ids),
                    AssetAssignment.end_date.is_(None)  # Только активные назначения
                )
                employees_result = await db.execute(employees_stmt)
                responsible_employees = [row[0] for row in employees_result.all()]

                # Отправляем уведомления
                for emp_id in responsible_employees:
                    await notify_inventory_started(
                        db=db,
                        employee_id=emp_id,
                        session_id=session_id,
                        initiator_id=session.created_by,  # Инициатором считается создатель сессии
                    )
                logger.info(f"[INVENTORY SCHEDULER] Отправлено {len(responsible_employees)} уведомлений о начале инвентаризации {session_id}")

            # 4. Сохраняем изменения
            await db.commit()
            logger.info(f"[INVENTORY SCHEDULER] Сессия {session_id} автоматически переведена в статус IN_PROGRESS")

    except Exception as e:
        logger.error(f"[INVENTORY SCHEDULER] Ошибка при запуске сессии {session_id}: {e}", exc_info=True)


async def complete_inventory_session_job(session_id: int):
    logger.info(f"[INVENTORY SCHEDULER] Запуск задачи complete_inventory_session_job для session_id={session_id}")
    try:
        async with async_session() as db:
            stmt = select(InventorizationSession).where(
                InventorizationSession.session_id == session_id,
                InventorizationSession.status == InventorizationStatus.IN_PROGRESS
            )
            result = await db.execute(stmt)
            session = result.scalar_one_or_none()

            if not session:
                logger.warning(f"[INVENTORY SCHEDULER] Сессия {session_id} не найдена или уже не в статусе IN_PROGRESS")
                return

            session.status = InventorizationStatus.COMPLETED
            await db.commit()
            logger.info(f"[INVENTORY SCHEDULER] Сессия {session_id} автоматически переведена в статус COMPLETED")
    except Exception as e:
        logger.error(f"[INVENTORY SCHEDULER] Ошибка при завершении сессии {session_id}: {e}", exc_info=True)