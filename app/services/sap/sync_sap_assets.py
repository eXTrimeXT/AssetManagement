import logging
import os
from datetime import datetime, date
from typing import Optional

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
import httpx
from fastapi import HTTPException
from dotenv import load_dotenv

from app.models.assets import Asset
from app.models.assets.AssetAssignment import AssetAssignment, AssignmentTypeEnum
from app.models.sap.SapDepartment import SapDepartment
from app.models.sap.SapMaterialClass import SapMaterialClass

load_dotenv()

logger = logging.getLogger(__name__)
SAP_API_URL = os.getenv("SAP_API_URL", "http://10.168.143.7:8123/sap/")
X_API_TOKEN = os.getenv("X_API_TOKEN")
headers = {"X-API-Token": X_API_TOKEN}


# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================
def _normalize_employee_id(raw) -> Optional[str]:
    """
    Приводит табельный номер к формату БД: 10 цифр с ведущими нулями.
    SAP отдаёт 8-значный ("00015370"), в БД хранится 10-значный ("0000015370").
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.isdigit():
        try:
            return str(int(s)).zfill(10)
        except (ValueError, OverflowError):
            return s
    return s


def _yyyymmdd_to_date_str(raw) -> Optional[str]:
    """'YYYYMMDD' → 'YYYY-MM-DD' (строка). None, если '00000000'/пусто."""
    if not raw:
        return None
    s = str(raw).strip()
    if s in ("", "00000000", "0") or len(s) != 8 or not s.isdigit():
        return None
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def _yyyymmdd_to_date(raw):
    """'YYYYMMDD' → datetime.date. None, если пусто/невалидно."""
    if not raw:
        return None
    s = str(raw).strip()
    if s in ("", "00000000", "0") or len(s) != 8 or not s.isdigit():
        return None
    try:
        return datetime.strptime(s, "%Y%m%d").date()
    except ValueError:
        return None


def _strip_or_none(v) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


# ==============================================================================
# СИНХРОНИЗАЦИЯ АКТИВОВ + ПРИВЯЗОК
# ==============================================================================
async def sync_sap_assets(db: AsyncSession, created_by: str = None) -> dict:
    """
    Синхронизация активов из SAP API с созданием локальных привязок пользователей.

    Что делает:
    1. Загружает батчами (limit=1000) через /base_materials.
    2. UPSERT активов по inventory_id (insert или update).
    3. UPSERT привязок AssetAssignment (assignment_type=USER) для каждого
       активного employee_id из SAP.
    4. Закрывает (end_date=today) привязки, которые больше не активны в SAP
       (для активов из текущей порции).

    Возвращает статистику.
    """
    logger.info("[SAP SYNC] Запуск синхронизации активов из SAP...")

    limit = 1000
    offset = 0
    total_assets = 0
    total_assignments_created = 0
    total_assignments_closed = 0
    total_skipped_batches = 0

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            while True:
                response = await client.get(
                    SAP_API_URL + "base_materials",
                    params={"limit": limit, "offset": offset},
                    # params={"limit": limit, "offset": offset, "serial_number": "SW-17"},
                    # params={"limit": limit, "offset": offset, "inventory_number": 100000005120},
                    headers=headers,
                    )

                if response.status_code == 422:
                    logger.error(f"[SAP SYNC] Ошибка валидации SAP API: {response.text}")
                    break

                response.raise_for_status()
                result = response.json()

                if (
                        not result.get("success")
                        or "response" not in result
                        or "data" not in result["response"]
                ):
                    logger.error("[SAP SYNC] Неверная структура ответа SAP API")
                    break

                data = result["response"]["data"]
                if not data:
                    break

                # ==============================================================
                # 1. Формируем записи для UPSERT активов
                # ==============================================================
                records_dict = {}
                for item in data:
                    inv_id = item.get("inventory_number")
                    if not inv_id:
                        continue

                    material_id = item.get("material_id") or None

                    raw_serial = item.get("long_serial_number") or item.get("serial_number")
                    serial_num = _strip_or_none(raw_serial)

                    # write_off_date: В БД VARCHAR → передаём ISO-строку
                    write_off_date_value = _yyyymmdd_to_date_str(item.get("write_off_date"))
                    # date_purchasing: В БД DATE → передаём datetime.date
                    date_purchasing_value = _yyyymmdd_to_date(item.get("changed_date"))

                    records_dict[inv_id] = {
                        "material_id": material_id,
                        "inventory_id": inv_id,
                        "name": item.get("base_material_name"),
                        "serial_number": serial_num,
                        "quantity": int(item.get("quantity", 0) or 0),

                        "cost_center_code_from": item.get("cost_center_code_from") or None,
                        "cost_center_name_from": item.get("cost_center_name_from") or None,
                        "cost_center_shortname_from": item.get("cost_center_shortname_from") or None,

                        "cost_center_code": item.get("cost_center_code") or None,
                        "cost_center_name": item.get("cost_center_name") or None,
                        "cost_center_shortname": item.get("cost_center_shortname") or None,

                        "material_class": item.get("material_class") or None,
                        "material_class_name": item.get("material_class_name") or None,

                        "date_purchasing": date_purchasing_value,
                        "write_off_date": write_off_date_value,

                        "every_week_check": False,
                        "created_by": created_by,
                        "updated_by": created_by,
                    }

                records = list(records_dict.values())
                if not records:
                    offset += limit
                    continue

                # ==============================================================
                # 2. UPSERT активов (insert или update по inventory_id)
                # ==============================================================
                try:
                    stmt = pg_insert(Asset).values(records)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["inventory_id"],
                        set_=dict(
                            material_id=stmt.excluded.material_id,
                            name=stmt.excluded.name,
                            serial_number=stmt.excluded.serial_number,
                            quantity=stmt.excluded.quantity,
                            cost_center_code_from=stmt.excluded.cost_center_code_from,
                            cost_center_name_from=stmt.excluded.cost_center_name_from,
                            cost_center_shortname_from=stmt.excluded.cost_center_shortname_from,
                            cost_center_code=stmt.excluded.cost_center_code,
                            cost_center_name=stmt.excluded.cost_center_name,
                            cost_center_shortname=stmt.excluded.cost_center_shortname,
                            material_class=stmt.excluded.material_class,
                            material_class_name=stmt.excluded.material_class_name,
                            date_purchasing=stmt.excluded.date_purchasing,
                            write_off_date=stmt.excluded.write_off_date,
                            updated_by=stmt.excluded.updated_by,
                        ),
                    )
                    await db.execute(stmt)
                    await db.commit()
                    total_assets += len(records)
                    logger.info(
                        f"[SAP SYNC] Активы: обработано {len(records)} (offset={offset})"
                    )
                except Exception as batch_err:
                    await db.rollback()
                    logger.error(
                        f"[SAP SYNC] Ошибка upsert активов (offset={offset}), пропускаем батч: {batch_err}"
                    )
                    total_skipped_batches += 1
                    offset += limit
                    continue

                # ==============================================================
                # 3. Получаем локальные asset_id для только что обработанных активов
                # ==============================================================
                batch_inv_ids = [r["inventory_id"] for r in records]
                mapping_result = await db.execute(
                    select(Asset.asset_id, Asset.inventory_id).where(
                        Asset.inventory_id.in_(batch_inv_ids)
                    )
                )
                asset_map = {row.inventory_id: row.asset_id for row in mapping_result.all()}

                # ==============================================================
                # 4. Формируем привязки пользователей (только для активных)
                #    - нормализуем employee_id
                #    - start_date = changed_date или сегодня
                #    - end_date = None, is_current = True
                # ==============================================================
                today = date.today()
                assignments_to_upsert = []
                # Для закрытия «пропавших» привязок — соберём список активных в SAP
                sap_active_pairs = set()  # (asset_id, employee_id)
                affected_asset_ids = set()

                for item in data:
                    inv_id = item.get("inventory_number")
                    raw_emp_id = item.get("employee_id")
                    if not inv_id or not raw_emp_id:
                        continue

                    emp_id = _normalize_employee_id(raw_emp_id)
                    if not emp_id:
                        continue

                    asset_id = asset_map.get(inv_id)
                    if not asset_id:
                        continue

                    # Дата начала: changed_date или сегодня
                    start_d = _yyyymmdd_to_date(item.get("changed_date")) or today

                    assignments_to_upsert.append({
                        "asset_id": asset_id,
                        "employee_id": emp_id,
                        "assignment_type": AssignmentTypeEnum.USER,
                        "start_date": start_d,
                        "end_date": None,
                        "is_current": True,
                        "assigned_by": created_by,
                    })
                    sap_active_pairs.add((asset_id, emp_id))
                    affected_asset_ids.add(asset_id)

                # ==============================================================
                # 5. UPSERT привязок
                # ==============================================================
                if assignments_to_upsert:
                    try:
                        assign_stmt = pg_insert(AssetAssignment).values(assignments_to_upsert)
                        assign_stmt = assign_stmt.on_conflict_do_update(
                            index_elements=["asset_id", "employee_id", "assignment_type"],
                            index_where=text("end_date IS NULL"),
                            set_=dict(
                                start_date=assign_stmt.excluded.start_date,
                                end_date=None,
                                is_current=True,
                                assigned_by=assign_stmt.excluded.assigned_by,
                            ),
                        )
                        await db.execute(assign_stmt)
                        await db.commit()
                        total_assignments_created += len(assignments_to_upsert)
                        logger.info(
                            f"[SAP SYNC] Привязки: обработано {len(assignments_to_upsert)} "
                            f"(offset={offset})"
                        )
                    except Exception as assign_err:
                        await db.rollback()
                        logger.error(
                            f"[SAP SYNC] Ошибка upsert привязок (offset={offset}): {assign_err} {asset_id=}"
                        )

                # ==============================================================
                # 6. Закрываем «пропавшие» привязки: активные USER-привязки,
                #    которых нет в SAP-данных этой порции → end_date = today
                # ==============================================================
                if affected_asset_ids:
                    # Получаем все активные USER-привязки для затронутых активов
                    active_assignments_result = await db.execute(
                        select(AssetAssignment).where(
                            AssetAssignment.asset_id.in_(affected_asset_ids),
                            AssetAssignment.assignment_type == AssignmentTypeEnum.USER,
                            AssetAssignment.end_date.is_(None),
                            )
                    )
                    active_assignments = active_assignments_result.scalars().all()

                    to_close_ids = []
                    for a in active_assignments:
                        if (a.asset_id, a.employee_id) not in sap_active_pairs:
                            to_close_ids.append(a.id if hasattr(a, 'id') else a.asset_assignment_id)

                    if to_close_ids:
                        try:
                            from sqlalchemy import update
                            await db.execute(
                                update(AssetAssignment)
                                .where(AssetAssignment.id.in_(to_close_ids))
                                .values(end_date=today, is_current=False)
                            )
                            await db.commit()
                            total_assignments_closed += len(to_close_ids)
                            logger.info(
                                f"[SAP SYNC] Закрыто привязок: {len(to_close_ids)} (offset={offset})"
                            )
                        except Exception as close_err:
                            await db.rollback()
                            logger.error(
                                f"[SAP SYNC] Ошибка закрытия привязок (offset={offset}): {close_err}"
                            )

                if len(data) < limit:
                    break
                offset += limit

        logger.info(
            f"[SAP SYNC] Синхронизация завершена. "
            f"Активов: {total_assets}, привязок создано/обновлено: {total_assignments_created}, "
            f"закрыто: {total_assignments_closed}, батчей с ошибкой: {total_skipped_batches}"
        )
        return {
            "success": True,
            "message": "Синхронизация завершена",
            "total_synced": total_assets,
            "total_assignments_synced": total_assignments_created,
            "total_assignments_closed": total_assignments_closed,
            "skipped_batches": total_skipped_batches,
        }

    except Exception as e:
        logger.error(
            f"[SAP SYNC] Критическая ошибка при синхронизации из SAP: {e}", exc_info=True
        )
        await db.rollback()
        return {
            "success": False,
            "message": f"Ошибка синхронизации: {str(e)}",
            "total_synced": total_assets,
        }


# ==============================================================================
# СПРАВОЧНИКИ
# ==============================================================================
async def get_sap_departments(
        limit: int = 1000,
        offset: int = 0,
        department: Optional[str] = None,
        department_name_like: Optional[str] = None,
) -> dict:
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
        language: str = "R",
) -> dict:
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
    logger.info("[SAP SYNC DEPARTMENTS] Запуск...")
    limit, offset, total_synced = 1000, 0, 0

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                response = await client.get(
                    SAP_API_URL + "mvz",
                    params={"limit": limit, "offset": offset},
                    headers=headers,
                    )
                if response.status_code == 422:
                    logger.error(f"[SAP SYNC DEPARTMENTS] Ошибка валидации SAP API: {response.text}")
                    break
                response.raise_for_status()
                result = response.json()
                if (
                        not result.get("success")
                        or "response" not in result
                        or "data" not in result["response"]
                ):
                    logger.error("[SAP SYNC DEPARTMENTS] Неверная структура ответа SAP API")
                    break
                data = result["response"]["data"]
                if not data:
                    break

                records = [
                    {
                        "department_code": str(item.get("department_code", "")).strip(),
                        "department_name": item.get("department_name"),
                        "department_shortname": item.get("department_shortname"),
                    }
                    for item in data
                ]
                if not records:
                    offset += limit
                    continue

                stmt = pg_insert(SapDepartment).values(records)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["department_code"],
                    set_=dict(
                        department_name=stmt.excluded.department_name,
                        department_shortname=stmt.excluded.department_shortname,
                        updated_at=func.now(),
                    ),
                )
                await db.execute(stmt)
                await db.commit()
                total_synced += len(records)
                logger.info(f"[SAP SYNC DEPARTMENTS] Обработано: {len(records)} (offset={offset})")
                if len(data) < limit:
                    break
                offset += limit

        logger.info(f"[SAP SYNC DEPARTMENTS] Завершено. Всего: {total_synced}")
        return {"success": True, "message": "Синхронизация подразделений завершена", "total_synced": total_synced}

    except Exception as e:
        logger.error(f"[SAP SYNC DEPARTMENTS] Критическая ошибка: {e}", exc_info=True)
        await db.rollback()
        return {"success": False, "message": f"Ошибка: {str(e)}", "total_synced": total_synced}


async def sync_sap_material_classes(db: AsyncSession, language: str = "R") -> dict:
    logger.info(f"[SAP SYNC CLASSES] Запуск (language={language})...")
    limit, offset, total_synced = 1000, 0, 0

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                response = await client.get(
                    SAP_API_URL + "search_material_classes",
                    params={"limit": limit, "offset": offset, "language": language},
                    headers=headers,
                    )
                if response.status_code == 422:
                    logger.error(f"[SAP SYNC CLASSES] Ошибка валидации SAP API: {response.text}")
                    break
                response.raise_for_status()
                result = response.json()
                if (
                        not result.get("success")
                        or "response" not in result
                        or "data" not in result["response"]
                ):
                    logger.error("[SAP SYNC CLASSES] Неверная структура ответа SAP API")
                    break
                data = result["response"]["data"]
                if not data:
                    break

                records = [
                    {
                        "material_class": str(item.get("material_class", "")).strip(),
                        "language": str(item.get("language", language)).strip(),
                        "material_class_short": item.get("material_class_short"),
                        "material_class_name": item.get("material_class_name"),
                    }
                    for item in data
                ]
                if not records:
                    offset += limit
                    continue

                stmt = pg_insert(SapMaterialClass).values(records)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["material_class", "language"],
                    set_=dict(
                        material_class_short=stmt.excluded.material_class_short,
                        material_class_name=stmt.excluded.material_class_name,
                        updated_at=func.now(),
                    ),
                )
                await db.execute(stmt)
                await db.commit()
                total_synced += len(records)
                logger.info(f"[SAP SYNC CLASSES] Обработано: {len(records)} (offset={offset})")
                if len(data) < limit:
                    break
                offset += limit

        logger.info(f"[SAP SYNC CLASSES] Завершено. Всего: {total_synced}")
        return {"success": True, "message": "Синхронизация классов материалов завершена", "total_synced": total_synced}

    except Exception as e:
        logger.error(f"[SAP SYNC CLASSES] Критическая ошибка: {e}", exc_info=True)
        await db.rollback()
        return {"success": False, "message": f"Ошибка: {str(e)}", "total_synced": total_synced}