import logging
import os
from datetime import datetime, date
from typing import Optional
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
import httpx
from fastapi import HTTPException
from dotenv import load_dotenv
from app.models.assets import Asset
from app.models.sap.SapDepartment import SapDepartment
from app.models.sap.SapMaterialClass import SapMaterialClass
from app.models.assets.AssetAssignment import AssetAssignment

load_dotenv()

logger = logging.getLogger(__name__)
SAP_API_URL = os.getenv("SAP_API_URL", "http://10.168.143.7:8123/sap/")  # default - test
X_API_TOKEN = os.getenv("X_API_TOKEN")
headers = {"X-API-Token": X_API_TOKEN}

async def sync_sap_assets(db: AsyncSession, created_by: str = "SAP_SYNC") -> dict:
    """
    Единая логика синхронизации активов из SAP API.
    Стратегия: Вставляет записи, сохраняя ВСЕ поля из SAP ответа, игнорируя конфликты уникальности.

    :param db: Активная сессия базы данных
    :param created_by: ID пользователя-инициатора синхронизации (по умолчанию "SAP_SYNC")
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
                    params={"limit": limit, "offset": offset},
                    headers=headers
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

                    material_id = item.get("material_id") or None

                    # === Обработка серийного номера ===
                    raw_serial = item.get("long_serial_number") or item.get("serial_number")
                    serial_num = raw_serial.strip() if isinstance(raw_serial, str) else raw_serial
                    if not serial_num:
                        serial_num = None

                    # === Обработка даты списания (формат YYYYMMDD или "00000000") ===
                    write_off_date_raw = item.get("write_off_date")
                    write_off_date = None
                    if write_off_date_raw and write_off_date_raw != "00000000" and len(str(write_off_date_raw)) == 8:
                        try:
                            write_off_date = datetime.strptime(str(write_off_date_raw), "%Y%m%d").date()
                        except ValueError:
                            write_off_date = None

                    # === Обработка даты изменения (changed_date) ===
                    changed_date_raw = item.get("changed_date")
                    date_purchasing = None
                    if changed_date_raw and len(str(changed_date_raw)) == 8:
                        try:
                            date_purchasing = datetime.strptime(str(changed_date_raw), "%Y%m%d").date()
                        except ValueError:
                            date_purchasing = None

                # Устраняем дубликаты inventory_id ВНУТРИ текущей порции от SAP
                records_dict = {}
                for item in data:
                    inv_id = item.get("inventory_number")
                    if not inv_id:
                        continue

                    material_id = item.get("material_id") or None

                    # === Обработка серийного номера ===
                    raw_serial = item.get("long_serial_number") or item.get("serial_number")
                    serial_num = raw_serial.strip() if isinstance(raw_serial, str) else raw_serial
                    if not serial_num:
                        serial_num = None

                    # === Обработка даты списания (write_off_date) ===
                    # В модели Asset это Column(String), поэтому мы НЕ делаем .date(), а оставляем строкой!
                    write_off_date_raw = item.get("write_off_date")
                    write_off_date = None
                    if write_off_date_raw and str(write_off_date_raw).strip() != "00000000":
                        s = str(write_off_date_raw).strip()
                        if len(s) == 8 and s.isdigit():
                            # Форматируем в красивый вид YYYY-MM-DD, но оставляем тип str
                            write_off_date = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
                        else:
                            write_off_date = s if s else None

                    # === Обработка даты изменения (changed_date) для date_purchasing ===
                    # В модели Asset это Column(Date), поэтому здесь .date() нужен и корректен
                    changed_date_raw = item.get("changed_date")
                    date_purchasing = None
                    if changed_date_raw and len(str(changed_date_raw)) == 8:
                        try:
                            date_purchasing = datetime.strptime(str(changed_date_raw), "%Y%m%d").date()
                        except ValueError:
                            date_purchasing = None

                    records_dict[inv_id] = {
                        # Основные идентификаторы
                        "material_id": material_id,
                        "inventory_id": inv_id,
                        "name": item.get("base_material_name"),
                        "serial_number": serial_num,
                        "quantity": int(item.get("quantity", 0) or 0), # Явный cast в int для безопасности

                        # Департаменты (ответственный)
                        "cost_center_code_from": item.get("cost_center_code_from") or None,
                        "cost_center_name_from": item.get("cost_center_name_from") or None,
                        "cost_center_shortname_from": item.get("cost_center_shortname_from") or None,

                        # Департаменты (владелец)
                        "cost_center_code": item.get("cost_center_code") or None,
                        "cost_center_name": item.get("cost_center_name") or None,
                        "cost_center_shortname": item.get("cost_center_shortname") or None,

                        # Класс материала
                        "material_class": item.get("material_class") or None,
                        "material_class_name": item.get("material_class_name") or None,

                        # Даты
                        "date_purchasing": date_purchasing,      # datetime.date (для Column(Date))
                        "write_off_date": write_off_date,        # str (для Column(String))

                        # Флаги
                        "every_week_check": False,

                        # Аудит
                        "created_by": "0000015370",
                        "updated_by": "0000015370",
                    }

                records = list(records_dict.values())
                if not records:
                    offset += limit
                    continue

                # Собираем все inventory_id из текущей порции для проверки в БД
                batch_inv_ids = [r["inventory_id"] for r in records]

                # Запрашиваем из БД существующие записи с такими inventory_id
                existing_query = select(Asset.asset_id, Asset.inventory_id).where(
                    Asset.inventory_id.in_(batch_inv_ids)
                )
                result_db = await db.execute(existing_query)
                existing_rows = result_db.all()

                existing_inv_ids = {row.inventory_id for row in existing_rows}

                # Фильтруем записи: оставляем только те, которых НЕТ в БД
                records_to_insert = [
                    r for r in records
                    if r["inventory_id"] not in existing_inv_ids
                ]

                # Безопасная вставка с игнорированием конфликтов
                if records_to_insert:
                    try:
                        stmt = pg_insert(Asset).values(records_to_insert)
                        stmt = stmt.on_conflict_do_nothing()

                        await db.execute(stmt)
                        await db.commit()

                        total_synced += len(records_to_insert)
                        logger.info(
                            f"[SAP SYNC] Обработано записей: {len(records_to_insert)} "
                            f"из {len(records)} в порции (offset={offset})"
                        )
                    except Exception as batch_err:
                        await db.rollback()
                        logger.error(
                            f"[SAP SYNC] Ошибка вставки батча (offset={offset}), пропускаем: {batch_err}"
                        )
                else:
                    logger.debug(
                        f"[SAP SYNC] В порции (offset={offset}) все записи уже существуют в БД, пропуск."
                    )

                if len(data) < limit:
                    break

                offset += limit

        logger.info(f"[SAP SYNC] Синхронизация завершена. Всего обработано записей: {total_synced}")
        return {
            "success": True,
            "message": "Синхронизация завершена",
            "total_synced": total_synced
        }

    except Exception as e:
        logger.error(f"[SAP SYNC] Критическая ошибка при синхронизации данных из SAP: {e}", exc_info=True)
        await db.rollback()
        return {
            "success": False,
            "message": f"Ошибка синхронизации: {str(e)}",
            "total_synced": total_synced
        }


# async def sync_sap_assets(db: AsyncSession, created_by: str = "0000015370") -> dict:
#     """
#     Единая логика синхронизации активов из SAP API.
#     Стратегия: Вставляет/обновляет записи, сохраняя ВСЕ поля из SAP,
#     и автоматически синхронизирует привязки пользователей (AssetAssignment).
#     """
#     logger.info("[SAP SYNC] Запуск синхронизации активов из SAP...")
#
#     limit = 1000
#     offset = 0
#     total_synced = 0
#     total_assignments_synced = 0
#
#     try:
#         async with httpx.AsyncClient() as client:
#             while True:
#                 response = await client.get(
#                     SAP_API_URL + "base_materials",
#                     params={"limit": limit, "offset": offset},
#                     headers=headers
#                 )
#
#                 if response.status_code == 422:
#                     logger.error(f"[SAP SYNC] Ошибка валидации SAP API: {response.text}")
#                     break
#
#                 response.raise_for_status()
#                 result = response.json()
#
#                 if not result.get("success") or "response" not in result or "data" not in result["response"]:
#                     logger.error("[SAP SYNC] Неверная структура ответа SAP API")
#                     break
#
#                 data = result["response"]["data"]
#                 if not data:
#                     break
#
#                 # 1. Формируем данные активов
#                 records_dict = {}
#                 for item in data:
#                     inv_id = item.get("inventory_number")
#                     if not inv_id:
#                         continue
#
#                     material_id = item.get("material_id") or None
#
#                     raw_serial = item.get("long_serial_number") or item.get("serial_number")
#                     serial_num = raw_serial.strip() if isinstance(raw_serial, str) else raw_serial
#                     if not serial_num:
#                         serial_num = None
#
#                     write_off_date_raw = item.get("write_off_date")
#                     write_off_date = None
#                     if write_off_date_raw and str(write_off_date_raw).strip() != "00000000":
#                         s = str(write_off_date_raw).strip()
#                         if len(s) == 8 and s.isdigit():
#                             write_off_date = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
#                         else:
#                             write_off_date = s if s else None
#
#                     changed_date_raw = item.get("changed_date")
#                     date_purchasing = None
#                     if changed_date_raw and len(str(changed_date_raw)) == 8:
#                         try:
#                             date_purchasing = datetime.strptime(str(changed_date_raw), "%Y%m%d").date()
#                         except ValueError:
#                             date_purchasing = None
#
#                     records_dict[inv_id] = {
#                         "material_id": material_id,
#                         "inventory_id": inv_id,
#                         "name": item.get("base_material_name"),
#                         "serial_number": serial_num,
#                         "quantity": int(item.get("quantity", 0) or 0),
#                         "cost_center_code_from": item.get("cost_center_code_from") or None,
#                         "cost_center_name_from": item.get("cost_center_name_from") or None,
#                         "cost_center_shortname_from": item.get("cost_center_shortname_from") or None,
#                         "cost_center_code": item.get("cost_center_code") or None,
#                         "cost_center_name": item.get("cost_center_name") or None,
#                         "cost_center_shortname": item.get("cost_center_shortname") or None,
#                         "material_class": item.get("material_class") or None,
#                         "material_class_name": item.get("material_class_name") or None,
#                         "date_purchasing": date_purchasing,
#                         "write_off_date": write_off_date,
#                         "every_week_check": False,
#                         "created_by": created_by,
#                         "updated_by": created_by,
#                     }
#
#                 records = list(records_dict.values())
#                 if not records:
#                     offset += limit
#                     continue
#
#                 batch_inv_ids = [r["inventory_id"] for r in records]
#
#                 # 2. Вставка или обновление активов
#                 if records:
#                     try:
#                         stmt = pg_insert(Asset).values(records)
#                         stmt = stmt.on_conflict_do_update(
#                             index_elements=["inventory_id"],
#                             set_=dict(
#                                 material_id=stmt.excluded.material_id,
#                                 name=stmt.excluded.name,
#                                 serial_number=stmt.excluded.serial_number,
#                                 quantity=stmt.excluded.quantity,
#                                 cost_center_code_from=stmt.excluded.cost_center_code_from,
#                                 cost_center_name_from=stmt.excluded.cost_center_name_from,
#                                 cost_center_shortname_from=stmt.excluded.cost_center_shortname_from,
#                                 cost_center_code=stmt.excluded.cost_center_code,
#                                 cost_center_name=stmt.excluded.cost_center_name,
#                                 cost_center_shortname=stmt.excluded.cost_center_shortname,
#                                 material_class=stmt.excluded.material_class,
#                                 material_class_name=stmt.excluded.material_class_name,
#                                 date_purchasing=stmt.excluded.date_purchasing,
#                                 write_off_date=stmt.excluded.write_off_date,
#                                 updated_by=stmt.excluded.updated_by,
#                             )
#                         )
#                         await db.execute(stmt)
#                         await db.commit()
#                         total_synced += len(records)
#                         logger.info(f"[SAP SYNC] Обработано активов: {len(records)} в порции (offset={offset})")
#                     except Exception as batch_err:
#                         await db.rollback()
#                         logger.error(f"[SAP SYNC] Ошибка вставки батча активов (offset={offset}), пропускаем: {batch_err}")
#
#                 # 3. СИНХРОНИЗАЦИЯ ПРИВЯЗОК ПОЛЬЗОВАТЕЛЕЙ (AssetAssignment)
#                 # Получаем локальные asset_id для всех inventory_id из текущей порции
#                 asset_mapping_query = select(Asset.asset_id, Asset.inventory_id).where(
#                     Asset.inventory_id.in_(batch_inv_ids)
#                 )
#                 asset_mapping_result = await db.execute(asset_mapping_query)
#                 asset_map = {row.inventory_id: row.asset_id for row in asset_mapping_result.all()}
#
#                 assignments_to_upsert = []
#                 today = date.today()
#
#                 for item in data:
#                     inv_id = item.get("inventory_number")
#                     raw_emp_id = str(item.get("employee_id", "")).strip()
#
#                     if not inv_id or not raw_emp_id:
#                         continue
#
#                     # Нормализация табельного номера (например, "6237" -> "00006237")
#                     emp_id = raw_emp_id.zfill(8)
#                     asset_id = asset_map.get(inv_id)
#
#                     if asset_id:
#                         assignments_to_upsert.append({
#                             "asset_id": asset_id,
#                             "employee_id": emp_id,
#                             "assignment_type": "user",  # SAP предоставляет основного пользователя
#                             "start_date": today,
#                             "end_date": None,
#                             "is_current": True,
#                             "assigned_by": created_by
#                         })
#
#                 # Массовый UPSERT привязок
#                 if assignments_to_upsert:
#                     try:
#                         assign_stmt = pg_insert(AssetAssignment).values(assignments_to_upsert)
#                         assign_stmt = assign_stmt.on_conflict_do_update(
#                             index_elements=["asset_id", "employee_id", "assignment_type"],
#                             set_=dict(
#                                 start_date=assign_stmt.excluded.start_date,
#                                 end_date=None,          # Реактивируем, если была закрыта
#                                 is_current=True,
#                                 assigned_by=assign_stmt.excluded.assigned_by
#                             )
#                         )
#                         await db.execute(assign_stmt)
#                         await db.commit()
#                         total_assignments_synced += len(assignments_to_upsert)
#                     except Exception as assign_err:
#                         await db.rollback()
#                         logger.error(f"[SAP SYNC] Ошибка вставки батча привязок (offset={offset}): {assign_err}")
#
#                 if len(data) < limit:
#                     break
#
#                 offset += limit
#
#         logger.info(
#             f"[SAP SYNC] Синхронизация завершена. "
#             f"Активов: {total_synced}, Привязок: {total_assignments_synced}"
#         )
#         return {
#             "success": True,
#             "message": "Синхронизация завершена",
#             "total_synced": total_synced,
#             "total_assignments_synced": total_assignments_synced
#         }
#
#     except Exception as e:
#         logger.error(f"[SAP SYNC] Критическая ошибка при синхронизации данных из SAP: {e}", exc_info=True)
#         await db.rollback()
#         return {
#             "success": False,
#             "message": f"Ошибка синхронизации: {str(e)}",
#             "total_synced": total_synced
#         }


async def get_sap_departments(
        limit: int = 1000,
        offset: int = 0,
        department: Optional[str] = None,
        department_name_like: Optional[str] = None
) -> dict:
    """Получение списка подразделений из SAP API."""
    sap_url = f"{SAP_API_URL}mvz"
    params = {"limit": limit, "offset": offset}

    if department:
        params["department"] = department
    if department_name_like:
        params["department_name_like"] = department_name_like

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(sap_url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as exc:
        logger.error(f"Ошибка соединения с SAP API (departments): {exc}")
        raise HTTPException(status_code=502, detail=f"Ошибка соединения с SAP API: {str(exc)}")
    except httpx.HTTPStatusError as exc:
        logger.error(f"Ошибка SAP API (departments): {exc.response.text}")
        raise HTTPException(status_code=exc.response.status_code, detail=f"Ошибка SAP API: {exc.response.text}")
    except Exception as exc:
        logger.error(f"Внутренняя ошибка сервера (departments): {exc}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(exc)}")


async def get_sap_asset_classes(
        limit: int = 200,
        offset: int = 0,
        language: str = "R"
) -> dict:
    """Получение списка классов активов из SAP API."""
    sap_url = f"{SAP_API_URL}search_material_classes"
    params = {"limit": limit, "offset": offset, "language": language}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(sap_url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as exc:
        logger.error(f"Ошибка соединения с SAP API (asset_classes): {exc}")
        raise HTTPException(status_code=502, detail=f"Ошибка соединения с SAP API: {str(exc)}")
    except httpx.HTTPStatusError as exc:
        logger.error(f"Ошибка SAP API (asset_classes): {exc.response.text}")
        raise HTTPException(status_code=exc.response.status_code, detail=f"Ошибка SAP API: {exc.response.text}")
    except Exception as exc:
        logger.error(f"Внутренняя ошибка сервера (asset_classes): {exc}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(exc)}")


async def sync_sap_departments(db: AsyncSession) -> dict:
    """
    Синхронизирует справочник подразделений (MVZ) из SAP API в таблицу sap_departments.
    Использует upsert (вставка или обновление) по первичному ключу department_code.
    """
    logger.info("[SAP SYNC DEPARTMENTS] Запуск синхронизации подразделений из SAP...")

    limit = 1000
    offset = 0
    total_synced = 0

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                response = await client.get(
                    SAP_API_URL + "mvz",
                    params={"limit": limit, "offset": offset},
                    headers=headers
                )

                if response.status_code == 422:
                    logger.error(f"[SAP SYNC DEPARTMENTS] Ошибка валидации SAP API: {response.text}")
                    break

                response.raise_for_status()
                result = response.json()

                if not result.get("success") or "response" not in result or "data" not in result["response"]:
                    logger.error("[SAP SYNC DEPARTMENTS] Неверная структура ответа SAP API")
                    break

                data = result["response"]["data"]
                if not data:
                    break

                # Формируем список записей для вставки
                # Внимание: имена ключей (department_code и т.д.) должны точно совпадать с ответом SAP API
                records = []
                for item in data:
                    records.append({
                        "department_code": str(item.get("department_code", "")).strip(),
                        "department_name": item.get("department_name"),
                        "department_shortname": item.get("department_shortname"),
                    })

                if not records:
                    offset += limit
                    continue

                # Upsert логика для PostgreSQL
                stmt = pg_insert(SapDepartment).values(records)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["department_code"],
                    set_=dict(
                        department_name=stmt.excluded.department_name,
                        department_shortname=stmt.excluded.department_shortname,
                        updated_at=func.now()
                    )
                )

                await db.execute(stmt)
                await db.commit()
                total_synced += len(records)
                logger.info(f"[SAP SYNC DEPARTMENTS] Обработано записей: {len(records)} (offset={offset})")

                if len(data) < limit:
                    break
                offset += limit

        logger.info(f"[SAP SYNC DEPARTMENTS] Синхронизация завершена. Всего обработано записей: {total_synced}")
        return {"success": True, "message": "Синхронизация подразделений завершена", "total_synced": total_synced}

    except Exception as e:
        logger.error(f"[SAP SYNC DEPARTMENTS] Критическая ошибка: {e}", exc_info=True)
        await db.rollback()
        return {"success": False, "message": f"Ошибка синхронизации: {str(e)}", "total_synced": total_synced}


async def sync_sap_material_classes(db: AsyncSession, language: str = "R") -> dict:
    """
    Синхронизирует справочник классов материалов из SAP API в таблицу sap_material_classes.
    Использует upsert по составному первичному ключу (material_class, language).
    """
    logger.info(f"[SAP SYNC CLASSES] Запуск синхронизации классов материалов из SAP (language={language})...")

    limit = 1000
    offset = 0
    total_synced = 0

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                response = await client.get(
                    SAP_API_URL + "search_material_classes",
                    params={"limit": limit, "offset": offset, "language": language},
                    headers=headers
                )

                if response.status_code == 422:
                    logger.error(f"[SAP SYNC CLASSES] Ошибка валидации SAP API: {response.text}")
                    break

                response.raise_for_status()
                result = response.json()

                if not result.get("success") or "response" not in result or "data" not in result["response"]:
                    logger.error("[SAP SYNC CLASSES] Неверная структура ответа SAP API")
                    break

                data = result["response"]["data"]
                if not data:
                    break

                records = []
                for item in data:
                    records.append({
                        "material_class": str(item.get("material_class", "")).strip(),
                        "language": str(item.get("language", language)).strip(),
                        "material_class_short": item.get("material_class_short"),
                        "material_class_name": item.get("material_class_name"),
                    })

                if not records:
                    offset += limit
                    continue

                # Upsert логика для PostgreSQL по составному ключу
                stmt = pg_insert(SapMaterialClass).values(records)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["material_class", "language"],
                    set_=dict(
                        material_class_short=stmt.excluded.material_class_short,
                        material_class_name=stmt.excluded.material_class_name,
                        updated_at=func.now()
                    )
                )

                await db.execute(stmt)
                await db.commit()
                total_synced += len(records)
                logger.info(f"[SAP SYNC CLASSES] Обработано записей: {len(records)} (offset={offset})")

                if len(data) < limit:
                    break
                offset += limit

        logger.info(f"[SAP SYNC CLASSES] Синхронизация завершена. Всего обработано записей: {total_synced}")
        return {"success": True, "message": "Синхронизация классов материалов завершена", "total_synced": total_synced}

    except Exception as e:
        logger.error(f"[SAP SYNC CLASSES] Критическая ошибка: {e}", exc_info=True)
        await db.rollback()
        return {"success": False, "message": f"Ошибка синхронизации: {str(e)}", "total_synced": total_synced}