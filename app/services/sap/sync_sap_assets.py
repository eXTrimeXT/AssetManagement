import logging
import os

from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from app.models.assets import Asset
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
SAP_API_URL = os.getenv("SAP_API_URL", "http://10.168.143.7:8123/sap/") # default - test

async def sync_sap_assets(db: AsyncSession) -> dict:
    """
    Единая логика синхронизации активов из SAP API.
    Стратегия: Вставляет записи, только если точной копии (по 4-м полям) еще нет в БД.
    Уникальные ограничения не требуются.

    :param db: Активная сессия базы данных
    :return: Словарь со статистикой выполнения
    """
    logger.info("[SAP SYNC] Запуск синхронизации активов из SAP...")

    limit = 1000
    offset = 0
    total_synced = 0

    try:
        async with httpx.AsyncClient() as client:
            while True:
                response = await client.get(
                    SAP_API_URL + "base_materials",
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

                # Устраняем дубликаты inventory_id ВНУТРИ текущей порции от SAP
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

                # Собираем все inventory_id из текущей порции для проверки в БД
                batch_inv_ids = [r["inventory_id"] for r in records]

                # Запрашиваем из БД существующие записи с такими inventory_id
                existing_query = select(
                    Asset.inventory_id,
                    Asset.name,
                    Asset.serial_number,
                    Asset.quantity
                ).where(Asset.inventory_id.in_(batch_inv_ids))

                result_db = await db.execute(existing_query)
                existing_rows = result_db.all()

                # Создаем множество (set) кортежей для мгновенного поиска O(1)
                existing_set = {
                    (row.inventory_id, row.name, (row.serial_number if row.serial_number else None), row.quantity)
                    for row in existing_rows
                }

                # Фильтруем записи: оставляем только те, которых НЕТ в БД в таком же виде
                records_to_insert = []
                for r in records:
                    serial_num = r["serial_number"] if r["serial_number"] else None
                    row_tuple = (r["inventory_id"], r["name"], serial_num, r["quantity"])

                    if row_tuple not in existing_set:
                        records_to_insert.append(r)

                # Вставляем только новые записи (обычный INSERT, без ON CONFLICT)
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

async def get_sap_departments():
    pass

async def get_sap_asset_classes(limit: int = 200, offset: int = 0, language: str = "R") -> dict:
    """
    Получение списка классов активов из SAP API.

    :param limit: Количество записей за один запрос
    :param offset: Смещение для пагинации
    :param language: Код языка (по умолчанию "R")
    :return: Словарь со списком классов активов и статистикой
    """
    logger.info("[SAP CLASSES] Запуск получения списка классов активов из SAP...")

    all_classes = []
    current_offset = offset

    try:
        async with httpx.AsyncClient() as client:
            while True:
                response = await client.get(
                    SAP_API_URL + "search_material_classes",
                    params={"limit": limit, "offset": current_offset, "language": language}
                )

                if response.status_code == 422:
                    logger.error(f"[SAP CLASSES] Ошибка валидации SAP API: {response.text}")
                    break

                response.raise_for_status()
                result = response.json()

                if not result.get("success") or "response" not in result or "data" not in result["response"]:
                    logger.error("[SAP CLASSES] Неверная структура ответа SAP API")
                    break

                data = result["response"]["data"]
                if not data:
                    break

                all_classes.extend(data)

                if len(data) < limit:
                    break

                current_offset += limit

        logger.info(f"[SAP CLASSES] Получение завершено. Всего получено записей: {len(all_classes)}")
        return {
            "success": True,
            "message": "Список классов активов получен",
            "data": all_classes,
            "total": len(all_classes)
        }

    except Exception as e:
        logger.error(f"[SAP CLASSES] Критическая ошибка при получении данных из SAP: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Ошибка получения: {str(e)}",
            "data": all_classes,
            "total": len(all_classes)
        }