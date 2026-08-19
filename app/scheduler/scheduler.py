import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from app.scheduler.jobs.service_check import check_service_assets

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def init_scheduler():
    """Инициализация планировщика"""

    # Запуск каждый день в 9:00
    scheduler.add_job(
        check_service_assets,
        # trigger=CronTrigger(hour=9, minute=0),
        # для быстрой проверки
        trigger=IntervalTrigger(minutes=30),
        id="service_check",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Планировщик запущен.")


def shutdown_scheduler():
    """Остановка планировщика"""
    scheduler.shutdown()
    logger.info("Планировщик остановлен.")