import io
import logging
import re
from datetime import date, datetime
from typing import Optional, Dict, Any, List

import pandas as pd
import httpx
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Response, Request
from sqlalchemy import select, or_, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.connection import get_db
from app.models.assets.Asset import Asset
from app.models.zup import Employee, ZupDepartment
from app.services.auth.auth_service import get_token_from_request, require_authorized_user
from app.schemas.assets.AssetSchemas import AssetCreate, AssetUpdate, BulkSaveRequest, AssetResponse
from app.database.assets.crud_asset import update_asset, create_asset
from app.database.assets.crud_asset_assignment import get_assignments_by_asset
from app.services.gps_rs.getinfouser import get_user_allowed_cost_centers
from app.services.ai.addon_asset_by_ai import addon_asset_by_agent

logger = logging.getLogger(__name__)

router_excel_import = APIRouter(prefix="/excel/assets", tags=["Assets"])
SAP_API_URL = "http://10.168.143.7:8123/sap/base_materials"

# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================
def clean_inventory_id(value: Any) -> Optional[str]:
    """Специальная очистка инвентарного номера."""
    if pd.isna(value) or value is None:
        return None
    val = str(value).strip()

    if val.lower() in ('nan', 'na', 'n/a', '?', 'не на балансе_ит', 'поставить на учет', 'new_поставить на учет'):
        return None

    if val.endswith('.0'):
        val = val[:-2]

    try:
        val = str(int(float(val)))
    except ValueError:
        pass

    return val.upper() if val else None

def normalize(value: Any) -> Optional[str]:
    if value is None:
        return None
    val_str = str(value).strip()
    if val_str == "" or val_str.lower() == "nan":
        return None
    return val_str.upper()

def parse_date(value: Any) -> Optional[date]:
    """
    Умный парсинг даты из Excel.
    - Извлекает самую раннюю дату из текста (например, "Акт 28.11.2025... Акт 22.08.2026")
    - Обрабатывает форматы DD.MM.YYYY и DD-MM-YYYY
    - Если найден только год (YYYY), преобразует его в YYYY-01-01
    """
    if pd.isna(value) or value is None or str(value).strip() == "":
        return None

    text = str(value).strip()

    # Паттерн для поиска полных дат: DD.MM.YYYY или DD-MM-YYYY
    pattern_full = r'\b(\d{2})[.\-](\d{2})[.\-](\d{4})\b'
    # Паттерн для поиска только года: YYYY (в диапазоне 1900-2099)
    pattern_year = r'\b(19\d{2}|20\d{2})\b'

    found_dates = []

    # Ищем полные даты
    for match in re.finditer(pattern_full, text):
        day, month, year = match.groups()
        try:
            dt = datetime.strptime(f"{day}.{month}.{year}", "%d.%m.%Y")
            found_dates.append(dt.date())
        except ValueError:
            pass

    # Если полных дат не найдено, ищем только год
    if not found_dates:
        for match in re.finditer(pattern_year, text):
            year = match.group(1)
            try:
                dt = datetime.strptime(year, "%Y")
                found_dates.append(dt.date())
            except ValueError:
                pass

    # Возвращаем самую раннюю найденную дату
    if found_dates:
        return min(found_dates)

    return None

def parse_int(value: Any) -> Optional[int]:
    if pd.isna(value) or value is None or str(value).strip() == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None

def parse_text(value: Any) -> Optional[str]:
    if pd.isna(value) or value is None:
        return None
    val_str = str(value).strip()
    return val_str if val_str.lower() != "nan" else None

async def find_asset_in_sap(inventory_id: Optional[str], serial_number: Optional[str]) -> Optional[Dict[str, Any]]:
    search_combinations = []
    if inventory_id and serial_number:
        search_combinations.append({"inventory_number": inventory_id, "serial_number": serial_number})
        search_combinations.append({"inventory_number": inventory_id})
        search_combinations.append({"serial_number": serial_number})
    elif inventory_id:
        search_combinations.append({"inventory_number": inventory_id})
    elif serial_number:
        search_combinations.append({"serial_number": serial_number})
    else:
        return None

    for params in search_combinations:
        params["limit"] = 10
        params["offset"] = 0
        params["employee_id_search_mode"] = "ALL"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(SAP_API_URL, params=params)
                response.raise_for_status()
                data = response.json()
                if data.get("success") and "data" in data.get("response", {}):
                    sap_items = data["response"]["data"]
                    if sap_items:
                        return sap_items[0]
        except Exception as e:
            logger.error(f"[SAP IMPORT] Ошибка при запросе к SAP API с params={params}: {e}")
            continue
    return None

async def _get_enriched_user(db: AsyncSession, employee_id: str, start_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Получает и обогащает данные пользователя из БД для предпросмотра."""
    if not employee_id:
        return None

    # Идеальное форматирование: дополняем нулями слева до 10 знаков (например, 1068 -> 0000001068)
    formatted_emp_id = str(employee_id).strip().zfill(10)

    stmt = select(Employee).options(
        selectinload(Employee.position),
        selectinload(Employee.group).options(
            selectinload(ZupDepartment.parent).options(
                selectinload(ZupDepartment.parent).options(
                    selectinload(ZupDepartment.parent)
                )
            )
        )
    ).where(Employee.employee_id == formatted_emp_id)

    result = await db.execute(stmt)
    employee = result.scalar_one_or_none()

    if not employee:
        return None

    # Построение иерархии подразделений
    hierarchy_chain = []
    current = employee.group
    while current is not None:
        hierarchy_chain.append(current)
        if not current.parent_guid or current.parent_guid == "00000000-0000-0000-0000-000000000000":
            break
        insp = inspect(current)
        parent_attr = insp.attrs.get('parent')
        if parent_attr is None or parent_attr.loaded_value is None:
            break
        current = parent_attr.loaded_value

    hierarchy_chain.reverse()
    employee.society = hierarchy_chain[0] if len(hierarchy_chain) >= 1 else None
    employee.department = hierarchy_chain[1] if len(hierarchy_chain) >= 2 else None
    employee.division = hierarchy_chain[2] if len(hierarchy_chain) >= 3 else None
    employee.group = hierarchy_chain[3] if len(hierarchy_chain) >= 4 else None

    parts_ru = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
    parts_en = [p for p in [employee.last_name_en, employee.first_name_en, employee.middle_name_en] if p]

    format_start_date = (
        str(start_date)[:4] + "-" + str(start_date)[4:6] + "-" + str(start_date)[6:]
        if start_date and len(str(start_date)) >= 8 else None
    )

    position_data = None
    if getattr(employee, 'position', None):
        position_data = {
            "name": employee.position.name,
            "name_en": employee.position.name_en,
        }

    def _get_dept_dict(dept_obj):
        if not dept_obj:
            return None
        return {
            "guid": dept_obj.guid,
            "name": dept_obj.name,
            "name_en": getattr(dept_obj, 'name_en', None),
            "short_name": getattr(dept_obj, 'short_name', None),
            "creation_date": getattr(dept_obj, 'creation_date', None),
            "closure_date": getattr(dept_obj, 'closure_date', None),
            "parent_guid": getattr(dept_obj, 'parent_guid', None),
        }

    return {
        "guid": employee.guid,
        "employee_id": employee.employee_id,
        "birth_date": employee.birth_date,
        "employment_date": employee.employment_date,
        "dismissal_date": employee.dismissal_date,
        "phone": employee.phone,
        "email": employee.email,
        "comment": employee.comment,
        "position_guid": employee.position_guid,
        "department_guid": employee.department_guid,
        "created_at": employee.__dict__.get('created_at'),
        "updated_at": employee.__dict__.get('updated_at'),
        "full_name_ru": " ".join(parts_ru) if parts_ru else None,
        "full_name_en": " ".join(parts_en) if parts_en else None,
        "society": _get_dept_dict(getattr(employee, 'society', None)),
        "department": _get_dept_dict(getattr(employee, 'department', None)),
        "division": _get_dept_dict(getattr(employee, 'division', None)),
        "group": _get_dept_dict(getattr(employee, 'group', None)),
        "position": position_data,
        "start_date": format_start_date,
        "end_date": None,
        "assignment_type": "user",
    }


# ==============================================================================
# ЛОГИКА ПРЕДВАРИТЕЛЬНОГО ПРОСМОТРА
# ==============================================================================
async def preview_excel_row(
        excel_row: Dict[str, Any],
        db: AsyncSession,
        allowed_cost_centers: List[str],
        row_index: int
) -> Dict[str, Any]:
    name = normalize(excel_row.get("name"))
    inv_id = clean_inventory_id(excel_row.get("inventory_id"))
    sn = normalize(excel_row.get("serial_number"))

    comment = parse_text(excel_row.get("comment"))
    date_issue = parse_date(excel_row.get("date_issue"))
    date_purchasing = parse_date(excel_row.get("date_purchasing"))
    next_service = parse_date(excel_row.get("next_service"))
    service_period = parse_int(excel_row.get("service_period"))
    check_period = parse_int(excel_row.get("check_period"))

    if not inv_id and not sn:
        return {
            "excel_row_index": row_index,
            "status": "skipped",
            "reason": "Нет корректного inventory_id или serial_number",
            "name": name, "inventory_id": inv_id, "serial_number": sn
        }

    # Поиск в локальной БД
    stmt = select(Asset).where(
        or_(
            Asset.inventory_id == inv_id,
            Asset.serial_number == sn
        )
    )
    result = await db.execute(stmt)
    local_asset = result.scalars().first()

    if local_asset:
        assignments = await get_assignments_by_asset(db=db, asset_id=local_asset.asset_id, active_only=True)
        employees = []
        if assignments:
            for assignment in assignments:
                logger.debug(f"Найдена привязка: assignment_id={assignment.id}, asset_id={assignment.asset_id}, emp_id={assignment.employee_id}")
                enriched_user = await _get_enriched_user(db, assignment.employee_id)
                if enriched_user:
                    employees.append(enriched_user)

        return {
            "excel_row_index": row_index,
            "status": "update",
            "asset_id": local_asset.asset_id,
            "name": local_asset.name or name,
            "inventory_id": local_asset.inventory_id or inv_id,
            "serial_number": local_asset.serial_number or sn,
            "quantity": 1,
            "comment": local_asset.comment or comment,
            "date_issue": local_asset.date_issue or date_issue,
            "date_purchasing": local_asset.date_purchasing or date_purchasing,
            "next_service": local_asset.next_service or next_service,
            "service_period": local_asset.service_period or service_period,
            "check_period": local_asset.check_period or check_period,
            "asset_type_id": local_asset.asset_type_id,
            "asset_status_id": local_asset.asset_status_id,
            "material_id": local_asset.material_id,
            "users": employees
        }

    # Поиск в SAP
    sap_asset = await find_asset_in_sap(inv_id, sn)

    if sap_asset:
        sap_cc = sap_asset.get("cost_center_code_from")
        if sap_cc:
            sap_cc_list = [c.strip().upper() for c in str(sap_cc).split(';') if c.strip()]
            has_permission = any(cc in allowed_cost_centers for cc in sap_cc_list)
            if not has_permission:
                return {
                    "excel_row_index": row_index,
                    "status": "no_permission",
                    "reason": f"Нет прав на импорт. cost_center_code_from в SAP: {sap_cc}",
                    "name": name, "inventory_id": inv_id, "serial_number": sn
                }

        sap_employee_id = sap_asset.get("employee_id")
        formatted_emp_id = str(sap_employee_id).strip().zfill(10) if sap_employee_id else None

        employees = []
        if formatted_emp_id:
            enriched_user = await _get_enriched_user(db, formatted_emp_id, sap_asset.get("changed_date"))
            if enriched_user:
                employees.append(enriched_user)

        return {
            "excel_row_index": row_index,
            "status": "create_from_sap",
            "asset_id": None,
            "name": sap_asset.get("base_material_name") or name or "Без имени",
            "inventory_id": sap_asset.get("inventory_number") or inv_id,
            "serial_number": sap_asset.get("serial_number") or sn,
            "quantity": int(sap_asset.get("quantity", 1)) if sap_asset.get("quantity") else 1,
            "comment": comment,
            "date_issue": date_issue,
            "date_purchasing": date_purchasing,
            "next_service": next_service,
            "service_period": service_period,
            "check_period": check_period,
            "material_id": sap_asset.get("material_id"),
            "cost_center_code_from": sap_asset.get("cost_center_code_from"),
            "cost_center_name_from": sap_asset.get("cost_center_name_from"),
            "cost_center_shortname_from": sap_asset.get("cost_center_shortname_from"),
            "cost_center_code": sap_asset.get("cost_center_code"),
            "cost_center_name": sap_asset.get("cost_center_name"),
            "cost_center_shortname": sap_asset.get("cost_center_shortname"),
            "asset_type_id": 0,
            "asset_status_id": 9,
            "users": employees
        }
        # Формируем временный объект AssetResponse для отправки в AI
    temp_asset = AssetResponse(
        name=name or "Без имени",
        inventory_id=inv_id or "UNKNOWN",
        serial_number=sn or "UNKNOWN",
        asset_type_id=0,
        asset_status_id=9,
        quantity=1
    )

    # Попытка обогатить данные через AI-агента
    model_name = manufacturer_name = asset_type_name = os_name = None
    try:
        enriched_data = await addon_asset_by_agent(temp_asset)
        model_name = enriched_data.get("model_name")
        manufacturer_name = enriched_data.get("manufacturer_name")
        asset_type_name = enriched_data.get("asset_type_name")
        os_name = enriched_data.get("os_name")
    except Exception as e:
        logger.error(f"Ошибка AI агента при обогащении актива (строка {row_index}): {e}")

    return {
        "excel_row_index": row_index,
        "status": "create_new",
        "asset_id": None,
        "name": name or "Без имени",
        "inventory_id": inv_id,
        "serial_number": sn,
        "quantity": 1,
        "comment": comment,
        "date_issue": date_issue,
        "date_purchasing": date_purchasing,
        "next_service": next_service,
        "service_period": service_period,
        "check_period": check_period,
        "asset_type_id": 0,
        "asset_status_id": 9,
        "model_name": model_name,
        "manufacturer_name": manufacturer_name,
        "asset_type_name": asset_type_name,
        "os_name": os_name,
        "users": None
    }
    # return {
    #     "excel_row_index": row_index,
    #     "status": "create_new",
    #     "asset_id": None,
    #     "name": name or "Без имени",
    #     "inventory_id": inv_id,
    #     "serial_number": sn,
    #     "quantity": 1,
    #     "comment": comment,
    #     "date_issue": date_issue,
    #     "date_purchasing": date_purchasing,
    #     "next_service": next_service,
    #     "service_period": service_period,
    #     "check_period": check_period,
    #     "asset_type_id": 0,
    #     "asset_status_id": 9,
    #     "users": None
    # }


# ==============================================================================
# ENDPOINTS
# ==============================================================================
@router_excel_import.post("/preview")
async def preview_import(
        request: Request,
        file: UploadFile = File(..., description="Excel файл для импорта"),
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    token = await get_token_from_request(request)

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы .xlsx или .xls")

    allowed_cost_centers = await get_user_allowed_cost_centers(token)
    if not allowed_cost_centers:
        raise HTTPException(status_code=403, detail="У пользователя нет прав (read/write) ни для одного department_code")

    contents = await file.read()

    try:
        # 1. Читаем сырые данные, чтобы получить оригинальные названия столбцов
        df_raw = pd.read_excel(io.BytesIO(contents), nrows=1)
        orig_cols = [str(c).strip() for c in df_raw.columns]

        # 2. Строим маппинг для dtype, чтобы защитить инвентарные и серийные номера от научной нотации
        dtype_mapping = {}
        for orig_col in orig_cols:
            col_lower = orig_col.lower().replace('\n', ' ')
            if 'инвентарный' in col_lower or 'серийный' in col_lower or 'тип и модель' in col_lower:
                dtype_mapping[orig_col] = str

        # 3. Читаем файл с защитой типов данных
        df = pd.read_excel(io.BytesIO(contents), dtype=dtype_mapping)

        # 4. Умное переименование столбцов (нечеткий поиск по ключевым словам)
        column_mapping_rules = {
            "инвентарный номер": "inventory_id",
            "Комментарий": "comment",
            "Комментарийарий": "comment",
            "тип и модель пк": "name",
            "название": "name",
            "серийный номер": "serial_number",
            "дата выдачи": "date_issue",
            "дата покупки": "date_purchasing",
            "дата обслуживания": "next_service",
            "период обслуживания": "service_period",
            "период проверки": "check_period",
        }

        new_columns = {}
        for col in df.columns:
            col_lower = str(col).strip().lower().replace('\n', ' ')
            for key, target_name in column_mapping_rules.items():
                if key in col_lower:
                    new_columns[col] = target_name
                    break

        df = df.rename(columns=new_columns)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения или парсинга Excel файла: {str(e)}")

    # Проверяем наличие хотя бы минимально необходимых столбцов после маппинга
    required_columns = {"inventory_id", "serial_number", "name"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"В файле не найдены обязательные данные. Убедитесь, что есть столбцы: Инвентарный номер, Серийный номер, Тип и модель ПК."
        )

    results = []
    for index, row in df.iterrows():
        excel_row = row.to_dict()
        try:
            preview_data = await preview_excel_row(
                excel_row=excel_row,
                db=db,
                allowed_cost_centers=allowed_cost_centers,
                row_index=index + 2
            )
            results.append(preview_data)
        except Exception as e:
            logger.error(f"Ошибка при предпросмотре строки {index + 2}: {e}", exc_info=True)
            results.append({
                "excel_row_index": index + 2,
                "status": "error",
                "reason": str(e),
                "name": normalize(excel_row.get("name")),
                "inventory_id": clean_inventory_id(excel_row.get("inventory_id")),
                "serial_number": normalize(excel_row.get("serial_number"))
            })

    return {
        "allowed_cost_centers_used": allowed_cost_centers,
        "total_rows": len(df),
        "items": results
    }


@router_excel_import.post("/bulk-save")
async def bulk_save_assets(
        request_data: BulkSaveRequest,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    """Массовое создание или обновление активов на основе данных, отредактированных на фронтенде."""
    results = []
    items = request_data.items

    for item_data in items:
        asset_id = item_data.get("asset_id")
        inv_id = item_data.get("inventory_id")
        sn = item_data.get("serial_number")
        material_id = item_data.get("material_id")
        item_asset_type_id = request_data.asset_type_id if request_data.asset_type_id else item_data.get("asset_type_id")
        logger.debug(f"{request_data.asset_type_id=} {item_data.get('asset_type_id')=} {item_asset_type_id=}")

        try:
            clean_data = {k: v for k, v in item_data.items() if k not in ["excel_row_index", "status", "reason", "asset_type_id"]}

            # Защита от UNIQUE VIOLATION
            if not asset_id:
                conditions = []
                if inv_id:
                    conditions.append(Asset.inventory_id == inv_id)
                if sn:
                    conditions.append(Asset.serial_number == sn)
                if material_id:
                    conditions.append(Asset.material_id == material_id)

                if conditions:
                    stmt = select(Asset.asset_id).where(or_(*conditions))
                    result = await db.execute(stmt)
                    existing_asset_id = result.scalar_one_or_none()

                    if existing_asset_id:
                        asset_id = existing_asset_id

            if asset_id:
                update_schema = AssetUpdate(asset_type_id=item_asset_type_id, **clean_data)
                await update_asset(db, asset_id, update_schema, current_user.employee_id)
                results.append({"asset_id": asset_id, "status": "updated", "success": True})
            else:
                create_schema = AssetCreate(asset_type_id=item_asset_type_id ,**clean_data)
                created_asset = await create_asset(db, create_schema, current_user.employee_id)
                results.append({
                    "asset_id": created_asset.asset_id if created_asset else None,
                    "status": "created",
                    "success": True
                })
        except Exception as e:
            await db.rollback()
            logger.error(f"Ошибка при сохранении актива {item_data.get('inventory_id')}: {e}", exc_info=True)
            results.append({
                "asset_id": asset_id,
                "status": "error",
                "success": False,
                "reason": str(e)
            })

    success_count = sum(1 for r in results if r["success"])
    return {
        "total_processed": len(items),
        "success_count": success_count,
        "error_count": len(items) - success_count,
        "details": results
    }


@router_excel_import.get("/import-template")
async def get_import_template():
    """Генерирует шаблон с ТОЧНЫМИ названиями столбцов из нового реестра."""
    columns = [
        "Инвентарный номер / Inventory number",
        "Тип и модель ПК / PC type and model",
        "Серийный номер / Serial Number",
        "Комментарий",
        "Дата выдачи / Issue Date",
        "Дата покупки / Purchasing Date",
        "Дата обслуживания / Service date",
        "Период обслуживания / Service period",
        "Период проверки / Check period"
    ]

    example_data = [
        {
            "Инвентарный номер / Inventory number": "0088",
            "Тип и модель ПК / PC type and model": "Ноутбук Dell Latitude 5520",
            "Серийный номер / Serial Number": "SN987654321",
            "Комментарий": "Выдан сотруднику отдела разработки",
            "Дата выдачи / Issue Date": "2023-10-01",
            "Дата покупки / Purchasing Date": "2023-09-15",
            "Дата обслуживания / Service date": "2024-10-01",
            "Период обслуживания / Service period": 365,
            "Период проверки / Check period": 30
        }
    ]

    df = pd.DataFrame(example_data, columns=columns)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Шаблон импорта")

    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=asset_import_template_new.xlsx"}
    )