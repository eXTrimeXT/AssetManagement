import logging
from app.database.connection import async_session
from app.services.zup.zup_integration import sync_all_data

logger = logging.getLogger(__name__)

async def sync_zup_data_job():
    """
    Фоновая задача для полной синхронизации справочников и сотрудников из 1С-ЗУП.
    """
    logger.info("[*] Запуск запланированной синхронизации данных из 1С-ЗУП...")
    try:
        # Создаем сессию вручную, так как мы находимся вне контекста HTTP-запроса
        async with async_session() as db:
            stats = await sync_all_data(db)
            logger.info(f"[+] Синхронизация 1С-ЗУП успешно завершена. Статистика: {stats}")
    except Exception as e:
        logger.error(f"[!] Критическая ошибка при синхронизации данных из 1С-ЗУП: {e}", exc_info=True)