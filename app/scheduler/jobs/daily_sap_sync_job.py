import logging
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import or_
import httpx
from app.database.connection import async_session
from app.models.assets import Asset

logger = logging.getLogger(__name__)


async def daily_sap_sync_job():
    """
    Плановая задача синхронизации активов из SAP API.
    Выполняет upsert, но пропускает обновление, если данные в БД полностью идентичны.
    """
    logger.info("[SAP SYNC] Запуск плановой синхронизации активов из SAP...")

    sap_api_url = "http://10.168.143.7:8123/sap/base_materials"
    limit = 1000
    offset = 0
    total_synced = 0

    try:
        async with async_session() as db:
            async with httpx.AsyncClient() as client:
                while True:
                    response = await client.get(
                        sap_api_url,
                        params={"limit": limit, "offset": offset}
                    )

                    if response.status_code == 422:
                        logger.error(f"[SAP SYNC] Ошибка валидации SAP API: {response.text}")
                        break

                    response.raise_for_status()
                    result = response.json()

                    if not result.get("success") or "response" not in result or "data" not in result["response"]:
                        logger.error("[SAP SYNC] Неверная структура ответа SAP API")
                        break

                    data = result["response"]["data"]
                    if not data:
                        break

                    # Удаляем дубликаты inventory_id внутри текущей порции
                    records_dict = {}
                    for item in data:
                        inv_id = item.get("inventory_number")
                        if not inv_id:
                            continue

                        serial_num = item.get("serial_number")
                        if not serial_num:
                            serial_num = None

                        records_dict[inv_id] = {
                            "inventory_id": inv_id,
                            "name": item.get("base_material_name"),
                            "serial_number": serial_num,
                            "quantity": item.get("quantity", 0)
                        }

                    records = list(records_dict.values())
                    if not records:
                        offset += limit
                        continue

                    # PostgreSQL bulk upsert
                    stmt = insert(Asset).values(records)

                    # Определяем условие: обновляем строку ТОЛЬКО если данные изменились.
                    # isnot_distinct_from корректно обрабатывает NULL значения в serial_number
                    condition_name_changed = Asset.name != stmt.excluded.name
                    condition_serial_changed = ~Asset.serial_number.isnot_distinct_from(stmt.excluded.serial_number)
                    condition_quantity_changed = Asset.quantity != stmt.excluded.quantity

                    update_where_clause = or_(
                        condition_name_changed,
                        condition_serial_changed,
                        condition_quantity_changed
                    )

                    stmt = stmt.on_conflict_do_update(
                        index_elements=["inventory_id"],
                        set_={
                            "name": stmt.excluded.name,
                            "serial_number": stmt.excluded.serial_number,
                            "quantity": stmt.excluded.quantity
                        },
                        where=update_where_clause  # <-- Ключевое условие пропуска идентичных строк
                    )

                    await db.execute(stmt)
                    await db.commit()

                    total_synced += len(records)
                    logger.info(f"[SAP SYNC] Обработана порция: {len(records)} записей (offset={offset})")

                    if len(data) < limit:
                        break

                    offset += limit

        logger.info(f"[SAP SYNC] Плановая синхронизация завершена. Всего проверено/обновлено записей: {total_synced}")

    except Exception as e:
        logger.error(f"[SAP SYNC] Критическая ошибка при синхронизации данных из SAP: {e}", exc_info=True)