import logging
from app.database.connection import async_session
from app.services.sap_sync_service.sync_sap_assets import sync_sap_assets

logger = logging.getLogger(__name__)


async def daily_sap_sync_job():
    """
    Плановая задача синхронизации активов из SAP API.
    Вызывает единый сервис синхронизации.
    """
    logger.info("[SAP SYNC] Запуск плановой фоновой синхронизации активов из SAP...")

    try:
        # Создаем сессию вручную, так как мы находимся вне контекста HTTP-запроса
        async with async_session() as db:
            result = await sync_sap_assets(db)

            if result.get("success"):
                logger.info(f"[SAP SYNC] Фоновая задача успешно завершена. Обработано записей: {result.get('total_synced')}")
            else:
                logger.error(f"[SAP SYNC] Фоновая задача завершилась с ошибкой: {result.get('message')}")

    except Exception as e:
        logger.error(f"[SAP SYNC] Критическая ошибка обертки фоновой задачи SAP: {e}", exc_info=True)