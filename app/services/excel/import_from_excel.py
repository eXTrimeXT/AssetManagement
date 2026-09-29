import io
import logging
from datetime import date
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
import pandas as pd
import httpx

from app.database.connection import get_db
from app.models.assets.Asset import Asset
from app.services.auth.auth_service import get_token_from_request, require_authorized_user
from app.schemas.assets.AssetSchemas import AssetCreate, AssetUpdate
from app.database.assets.crud_asset import update_asset, create_asset

from app.services.gps_rs.getinfouser import get_user_allowed_cost_centers

logger = logging.getLogger(__name__)

router_excel_import = APIRouter(prefix="/excel/assets", tags=["Assets"])

SAP_API_URL = "http://10.168.143.7:8123/sap/base_materials"

# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================
def normalize(value: Any) -> Optional[str]:
    if value is None:
        return None
    val_str = str(value).strip()
    if val_str == "" or val_str.lower() == "nan":
        return None
    return val_str.upper()

def parse_date(value: Any) -> Optional[date]:
    if pd.isna(value) or value is None or str(value).strip() == "":
        return None
    try:
        return pd.to_datetime(value).date()
    except Exception:
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

# ==============================================================================
# ЛОГИКА ПРЕДВАРИТЕЛЬНОГО ПРОСМОТРА (БЕЗ СОХРАНЕНИЯ В БД)
# ==============================================================================
async def preview_excel_row(
        excel_row: Dict[str, Any],
        db: AsyncSession,
        allowed_cost_centers: List[str],
        row_index: int
) -> Dict[str, Any]:
    name = normalize(excel_row.get("Название"))
    inv_id = normalize(excel_row.get("Инвентарный номер"))
    sn = normalize(excel_row.get("Серийный номер"))

    quantity = parse_int(excel_row.get("Количество"))
    comment = parse_text(excel_row.get("Комментарий"))
    date_issue = parse_date(excel_row.get("Дата выпуска"))
    date_purchasing = parse_date(excel_row.get("Дата покупки"))
    next_service = parse_date(excel_row.get("Дата обслуживания"))
    service_period = parse_int(excel_row.get("Период обслуживания"))
    check_period = parse_int(excel_row.get("Период проверки"))

    if not inv_id and not sn:
        return {
            "excel_row_index": row_index,
            "status": "skipped",
            "reason": "Нет inventory_id и serial_number",
            "name": name, "inventory_id": inv_id, "serial_number": sn
        }

    # Поиск в локальной БД
    stmt = select(Asset).where(or_(Asset.inventory_id == inv_id, Asset.serial_number == sn))
    result = await db.execute(stmt)
    local_asset = result.scalar_one_or_none()

    if local_asset:
        # Слияние: Локальная БД + перезапись полями из Excel, если они есть
        return {
            "excel_row_index": row_index,
            "status": "update",
            "asset_id": local_asset.asset_id,
            "name": name or local_asset.name,
            "inventory_id": inv_id or local_asset.inventory_id,
            "serial_number": sn or local_asset.serial_number,
            "quantity": quantity if quantity is not None else local_asset.quantity,
            "comment": comment if comment else local_asset.comment,
            "date_issue": date_issue or local_asset.date_issue,
            "date_purchasing": date_purchasing or local_asset.date_purchasing,
            "next_service": next_service or local_asset.next_service,
            "service_period": service_period if service_period is not None else local_asset.service_period,
            "check_period": check_period if check_period is not None else local_asset.check_period,
            "asset_type_id": local_asset.asset_type_id,
            "asset_status_id": local_asset.asset_status_id,
            "material_id": local_asset.material_id,
        }

    # Поиск в SAP
    sap_asset = await find_asset_in_sap(inv_id, sn)

    if sap_asset:
        # Проверка прав
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

        # Слияние: SAP + перезапись полями из Excel
        return {
            "excel_row_index": row_index,
            "status": "create_from_sap",
            "asset_id": None, # Новый актив
            "name": name or sap_asset.get("base_material_name") or "Без имени",
            "inventory_id": inv_id or sap_asset.get("inventory_number"),
            "serial_number": sn or sap_asset.get("serial_number"),
            "quantity": quantity if quantity is not None else (int(sap_asset.get("quantity", 1)) if sap_asset.get("quantity") else 1),
            "comment": comment, # Только из Excel
            "date_issue": date_issue, # Только из Excel
            "date_purchasing": date_purchasing, # Только из Excel
            "next_service": next_service, # Только из Excel
            "service_period": service_period, # Только из Excel
            "check_period": check_period, # Только из Excel
            "material_id": sap_asset.get("material_id"),
            "cost_center_code_from": sap_asset.get("cost_center_code_from"),
            "cost_center_name_from": sap_asset.get("cost_center_name_from"),
            "cost_center_shortname_from": sap_asset.get("cost_center_shortname_from"),
            "cost_center_code": sap_asset.get("cost_center_code"),
            "cost_center_name": sap_asset.get("cost_center_name"),
            "cost_center_shortname": sap_asset.get("cost_center_shortname"),
            "asset_type_id": 0,
            "asset_status_id": 9,
        }

    # Не найдено нигде
    return {
        "excel_row_index": row_index,
        "status": "create_new",
        "asset_id": None,
        "name": name or "Без имени",
        "inventory_id": inv_id,
        "serial_number": sn,
        "quantity": quantity if quantity is not None else 1,
        "comment": comment,
        "date_issue": date_issue,
        "date_purchasing": date_purchasing,
        "next_service": next_service,
        "service_period": service_period,
        "check_period": check_period,
        "asset_type_id": 0,
        "asset_status_id": 9,
    }

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
    """Читает Excel, сливает с SAP/Local DB и возвращает список для предпросмотра на фронтенде."""
    token = await get_token_from_request(request)

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы .xlsx или .xls")

    allowed_cost_centers = await get_user_allowed_cost_centers(token)
    if not allowed_cost_centers:
        raise HTTPException(status_code=403, detail="У пользователя нет прав (read/write) ни для одного department_code")

    contents = await file.read()
    try:
        df = pd.read_excel(
            io.BytesIO(contents),
            dtype={"Название": str, "Инвентарный номер": str, "Серийный номер": str}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения Excel файла: {str(e)}")

    required_columns = {"Название", "Инвентарный номер", "Серийный номер", "Количество"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise HTTPException(status_code=400, detail=f"В файле отсутствуют обязательные колонки: {missing_columns}")

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
                "name": normalize(excel_row.get("Название")),
                "inventory_id": normalize(excel_row.get("Инвентарный номер")),
                "serial_number": normalize(excel_row.get("Серийный номер"))
            })

    return {
        "allowed_cost_centers_used": allowed_cost_centers,
        "total_rows": len(df),
        "items": results # Возвращаем как items, чтобы фронтенд мог использовать тот же интерфейс, что и для get_assets
    }


@router_excel_import.post("/bulk-save")
async def bulk_save_assets(
        items: List[Dict[str, Any]], # Фронтенд пришлет массив объектов, похожих на AssetCreate/AssetUpdate
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    """Массовое создание или обновление активов на основе данных, отредактированных на фронтенде."""
    results = []

    for item_data in items:
        asset_id = item_data.get("asset_id")

        try:
            # Исключаем служебные поля предпросмотра перед передачей в схемы
            clean_data = {k: v for k, v in item_data.items() if k not in ["excel_row_index", "status", "reason"]}

            if asset_id:
                # === ОБНОВЛЕНИЕ СУЩЕСТВУЮЩЕГО ===
                # Преобразуем в AssetUpdate (используем exclude_unset=True внутри update_asset)
                update_schema = AssetUpdate(**clean_data)
                updated_asset = await update_asset(db, asset_id, update_schema, current_user.employee_id)
                results.append({
                    "asset_id": asset_id,
                    "status": "updated",
                    "success": True
                })
            else:
                # === СОЗДАНИЕ НОВОГО ===
                create_schema = AssetCreate(**clean_data)
                created_asset = await create_asset(db, create_schema, current_user.employee_id)
                results.append({
                    "asset_id": created_asset.asset_id if created_asset else None,
                    "status": "created",
                    "success": True
                })
        except Exception as e:
            await db.rollback() # Откат на случай ошибки валидации или БД
            logger.error(f"Ошибка при сохранении актива {item_data.get('inventory_id')}: {e}", exc_info=True)
            results.append({
                "asset_id": asset_id,
                "status": "error",
                "success": False,
                "reason": str(e)
            })

    # Финальный коммит не нужен здесь, т.к. create_asset и update_asset уже делают commit внутри себя.
    # Если потребуется оптимизация (один коммит на все), логику create/update нужно будет немного изменить,
    # но текущий вариант гарантирует корректную работу триггеров, истории и уведомлений.

    success_count = sum(1 for r in results if r["success"])
    return {
        "total_processed": len(items),
        "success_count": success_count,
        "error_count": len(items) - success_count,
        "details": results
    }


@router_excel_import.get("/import-template")
async def get_import_template():
    """Генерирует и отдает Excel-шаблон с русскими заголовками и примером заполнения."""
    columns = [
        "Название", "Инвентарный номер", "Серийный номер", "Количество",
        "Комментарий", "Дата выпуска", "Дата покупки", "Дата обслуживания",
        "Период обслуживания", "Период проверки"
    ]

    example_data = [
        {
            "Название": "Ноутбук Dell Latitude 5520",
            "Инвентарный номер": "0088",
            "Серийный номер": "SN987654321",
            "Количество": 1,
            "Комментарий": "Выдан сотруднику",
            "Дата выпуска": "2023-10-01",
            "Дата покупки": "2023-09-15",
            "Дата обслуживания": "2024-10-01",
            "Период обслуживания": 365,
            "Период проверки": 30
        }
    ]

    df = pd.DataFrame(example_data, columns=columns)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Шаблон импорта")

    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=asset_import_template.xlsx"}
    )