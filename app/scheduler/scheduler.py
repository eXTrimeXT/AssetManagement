import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.scheduler.jobs.sync_zup_data import sync_zup_data_job
from app.scheduler.jobs.asset_service_check import check_service_assets

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def init_scheduler():
    """Инициализация планировщика"""

    scheduler.add_job(
        check_service_assets,
        # trigger=CronTrigger(hour=9, minute=0),
        # для быстрой проверки
        trigger=IntervalTrigger(minutes=20),
        id="asset_service_check",
        replace_existing=True,
    )

    scheduler.add_job(
        func=sync_zup_data_job,
        trigger=CronTrigger(hour=2),
        # trigger=IntervalTrigger(minutes=1),
        id="sync_all_data",
        replace_existing=True,
        max_instances=1,  # Запретить параллельные запуски
        coalesce=True,    # Если пропущен запуск, выполнить только один раз
        misfire_grace_time=3600  # Допустимая задержка запуска (1 час)
    )

    scheduler.start()
    logger.info("Планировщик запущен.")


def shutdown_scheduler():
    """Остановка планировщика"""
    scheduler.shutdown()
    logger.info("Планировщик остановлен.")