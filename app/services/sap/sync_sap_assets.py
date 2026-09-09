import logging
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from app.models.assets import Asset

logger = logging.getLogger(__name__)


async def sync_sap_assets(db: AsyncSession) -> dict:
    """
    Единая логика синхронизации активов из SAP API.
    Стратегия: Вставляет записи, только если точной копии (по 4-м полям) еще нет в БД.
    Уникальные ограничения не требуются.

    :param db: Активная сессия базы данных
    :return: Словарь со статистикой выполнения
    """
    logger.info("[SAP SYNC] Запуск синхронизации активов из SAP...")

    sap_api_url = "http://10.168.143.7:8123/sap/base_materials"
    limit = 1000
    offset = 0
    total_synced = 0

    try:
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

                # 1. Устраняем дубликаты inventory_id ВНУТРИ текущей порции от SAP
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
                        "quantity": item.get("quantity", 0),
                        "every_week_check": False
                    }

                records = list(records_dict.values())
                if not records:
                    offset += limit
                    continue

                # 2. Собираем все inventory_id из текущей порции для проверки в БД
                batch_inv_ids = [r["inventory_id"] for r in records]

                # 3. Запрашиваем из БД существующие записи с такими inventory_id
                existing_query = select(
                    Asset.inventory_id,
                    Asset.name,
                    Asset.serial_number,
                    Asset.quantity
                ).where(Asset.inventory_id.in_(batch_inv_ids))

                result_db = await db.execute(existing_query)
                existing_rows = result_db.all()

                # 4. Создаем множество (set) кортежей для мгновенного поиска O(1)
                existing_set = {
                    (row.inventory_id, row.name, (row.serial_number if row.serial_number else None), row.quantity)
                    for row in existing_rows
                }

                # 5. Фильтруем записи: оставляем только те, которых НЕТ в БД в таком же виде
                records_to_insert = []
                for r in records:
                    serial_num = r["serial_number"] if r["serial_number"] else None
                    row_tuple = (r["inventory_id"], r["name"], serial_num, r["quantity"])

                    if row_tuple not in existing_set:
                        records_to_insert.append(r)

                # 6. Вставляем только новые записи (обычный INSERT, без ON CONFLICT)
                if records_to_insert:
                    stmt = insert(Asset).values(records_to_insert)
                    await db.execute(stmt)
                    await db.commit()
                    total_synced += len(records_to_insert)
                    logger.info(f"[SAP SYNC] Вставлено новых записей: {len(records_to_insert)} из {len(records)} в порции (offset={offset})")
                else:
                    logger.debug(f"[SAP SYNC] В порции (offset={offset}) все записи уже существуют в БД, пропуск.")

                if len(data) < limit:
                    break

                offset += limit

        logger.info(f"[SAP SYNC] Синхронизация завершена. Всего добавлено записей: {total_synced}")
        return {"success": True, "message": "Синхронизация завершена", "total_synced": total_synced}

    except Exception as e:
        logger.error(f"[SAP SYNC] Критическая ошибка при синхронизации данных из SAP: {e}", exc_info=True)
        return {"success": False, "message": f"Ошибка синхронизации: {str(e)}", "total_synced": total_synced}