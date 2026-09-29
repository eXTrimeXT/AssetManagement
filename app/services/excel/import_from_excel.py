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

logger = logging.getLogger(__name__)

router_excel_import = APIRouter(prefix="/excel/assets", tags=["Assets"])

SAP_API_URL = "http://10.168.143.7:8123/sap/base_materials"

# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
def normalize(value: Any) -> Optional[str]:
    """
    Нормализация: убирает пробелы, приводит к верхнему регистру,
    пустоту и pandas 'nan' превращает в None.
    """
    if value is None:
        return None

    val_str = str(value).strip()

    if val_str == "" or val_str.lower() == "nan":
        return None

    return val_str.upper()

def parse_date(value: Any) -> Optional[date]:
    """
    Безопасный парсинг даты из Excel.
    Возвращает объект datetime.date (требуется для asyncpg DATE колонок), а не строку.
    Корректно обрабатывает строки 'YYYY-MM-DD' и числовые форматы дат Excel.
    """
    if pd.isna(value) or value is None or str(value).strip() == "":
        return None
    try:
        dt = pd.to_datetime(value)
        return dt.date()
    except Exception:
        return None

def parse_int(value: Any) -> Optional[int]:
    """Безопасный парсинг целого числа (обрабатывает float из pandas и NaN)."""
    if pd.isna(value) or value is None or str(value).strip() == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None

def parse_text(value: Any) -> Optional[str]:
    """Безопасный парсинг обычного текста (без upper(), но с защитой от NaN)."""
    if pd.isna(value) or value is None:
        return None
    val_str = str(value).strip()
    return val_str if val_str.lower() != "nan" else None

async def get_user_allowed_cost_centers(token: str) -> List[str]:
    """
    Получает СПИСОК всех department_code, где у пользователя есть read=true и write=true.
    """
    url = "http://gps-test.hmmr.ru/api/getinfouser"

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(url, json={"token": token})
        response.raise_for_status()
        data = response.json()
        logger.info(f"getinfouser: {data=}")

    allowed_codes = []
    for perm in data.get("permission_departments", []):
        if perm.get("read") is True and perm.get("write") is True:
            code = perm.get("department_code")
            if code:
                allowed_codes.append(str(code).strip().upper())

    return allowed_codes

async def find_asset_in_sap(
        inventory_id: Optional[str],
        serial_number: Optional[str]
) -> Optional[Dict[str, Any]]:
    """
    Ищет актив в SAP, перебирая комбинации параметров.
    Это гарантирует поиск, даже если в SAP заполнен только инвентарный
    или только серийный номер.
    """
    search_combinations = []

    if inventory_id and serial_number:
        # 1. Точное совпадение по обоим полям (на случай, если SAP это поддерживает)
        search_combinations.append({"inventory_number": inventory_id, "serial_number": serial_number})
        # 2. Только по инвентарному номеру
        search_combinations.append({"inventory_number": inventory_id})
        # 3. Только по серийному номеру
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
                        # Возвращаем первое найденное совпадение
                        logger.info(f"совпадение = {sap_items[0]=}")
                        return sap_items[0]

        except Exception as e:
            logger.error(f"[SAP IMPORT] Ошибка при запросе к SAP API с params={params}: {e}")
            continue

    return None

# ОСНОВНАЯ ЛОГИКА ОБРАБОТКИ СТРОКИ
async def process_excel_row(
        excel_row: Dict[str, Any],
        db: AsyncSession,
        allowed_cost_centers: List[str],
        employee_id: str
):
    # Извлечение и нормализация полей из Excel
    name            = normalize(excel_row.get("Название"))
    inv_id          = normalize(excel_row.get("Инвентарный номер"))
    sn              = normalize(excel_row.get("Серийный номер"))
    quantity        = parse_int(excel_row.get("Количество"))
    comment         = parse_text(excel_row.get("Комментарий"))
    date_issue      = parse_date(excel_row.get("Дата выпуска"))
    date_purchasing = parse_date(excel_row.get("Дата покупки"))
    next_service    = parse_date(excel_row.get("Дата обслуживания"))
    service_period  = parse_int(excel_row.get("Период обслуживания"))
    check_period    = parse_int(excel_row.get("Период проверки"))
    # cost_center_code_from = excel_row.get("cost_center_code_from")
    # cost_center_name_from = excel_row.get("cost_center_name_from")
    # cost_center_shortname_from = excel_row.get("cost_center_shortname_from")
    # cost_center_code = excel_row.get("cost_center_shortname_from")
    # cost_center_name = excel_row.get("cost_center_shortname_from")
    # cost_center_shortname = excel_row.get("cost_center_shortname_from")

    if not inv_id and not sn:
        return {"status": "skipped", "reason": "Нет inventory_id и serial_number"}

    # Поиск в локальной БД
    stmt = select(Asset).where(
        or_(
            Asset.inventory_id == inv_id,
            Asset.serial_number == sn
        )
    )
    result = await db.execute(stmt)
    local_asset = result.scalar_one_or_none()

    # Поиск в SAP (перебирает варианты запросов, чтобы найти актив)
    sap_asset = await find_asset_in_sap(inv_id, sn)

    # ПРОВЕРКА ПРАВ ПО COST CENTER
    if sap_asset:
        sap_cc = sap_asset.get("cost_center_code_from")
        if sap_cc:
            # SAP может вернуть несколько кодов через точку с запятой
            sap_cc_list = [c.strip().upper() for c in str(sap_cc).split(';') if c.strip()]

            # Проверяем, есть ли ХОТЯ БЫ ОДИН разрешенный код в списке из SAP
            has_permission = any(cc in allowed_cost_centers for cc in sap_cc_list)

            if not has_permission:
                return {
                    "status": "skipped",
                    "reason": f"Нет прав на импорт. cost_center_code_from в SAP: {sap_cc}"
                }

    # Матрица решений
    if local_asset:
        local_asset.name             = name            if name            else local_asset.name
        local_asset.inventory_id     = inv_id          if inv_id          else local_asset.inventory_id
        local_asset.serial_number    = sn              if sn              else local_asset.serial_number
        local_asset.quantity         = quantity        if quantity        else local_asset.quantity
        local_asset.comment          = comment         if comment         else local_asset.comment
        local_asset.every_week_check = False
        local_asset.date_issue       = date_issue      if date_issue      else local_asset.data_issue
        local_asset.date_purchasing  = date_purchasing if date_purchasing else local_asset.date_purchasing
        local_asset.next_service     = next_service    if next_service    else local_asset.next_service
        local_asset.service_period   = service_period  if service_period  else local_asset.service_period
        local_asset.check_period     = check_period    if check_period    else local_asset.check_period
        local_asset.updated_by       = employee_id     if employee_id     else local_asset.updated_by

        await db.commit()
        await db.refresh(local_asset)
        return {"status": "updated", "asset_id": local_asset.asset_id, "from_sap": False}

    else:
        # Создаем новую запись
        base_data = sap_asset if sap_asset else {}

        new_asset = Asset(
            name=name or base_data.get("base_material_name") or "Без имени",
            inventory_id=inv_id or base_data.get("inventory_number"),
            serial_number=sn or base_data.get("serial_number"),
            quantity=int(quantity) if quantity is not None else (int(base_data.get("quantity", 1)) if base_data.get("quantity") else 1),
            material_id=base_data.get("material_id"),
            every_week_check=False,
            comment=comment,                    # Данные брать только из Excel
            date_issue=date_issue,              # Данные брать только из Excel
            date_purchasing=date_purchasing,    # Данные брать только из Excel
            next_service=next_service,          # Данные брать только из Excel
            service_period=service_period,      # Данные брать только из Excel
            check_period=check_period,          # Данные брать только из Excel
            created_by=employee_id,             # Кто создал актив
            cost_center_code_from=base_data.get("cost_center_code_from"),
            cost_center_name_from=base_data.get("cost_center_name_from"),
            cost_center_shortname_from=base_data.get("cost_center_shortname_from"),
            cost_center_code=base_data.get("cost_center_code"),
            cost_center_name=base_data.get("cost_center_name"),
            cost_center_shortname=base_data.get("cost_center_shortname"),

            # Тип и статус по умолчанию
            asset_type_id=0,
            asset_status_id=9,
        )

        db.add(new_asset)
        await db.commit()
        await db.refresh(new_asset)
        return {"status": "created", "asset_id": new_asset.asset_id, "from_sap": True}

@router_excel_import.post("/import")
async def import_from_excel(
        request: Request,
        file: UploadFile = File(..., description="Excel файл для импорта"),
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    token = await get_token_from_request(request)

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы .xlsx или .xls")

    # Получаем список разрешенных cost_center_code
    allowed_cost_centers = await get_user_allowed_cost_centers(token)
    if not allowed_cost_centers:
        raise HTTPException(status_code=403, detail="У пользователя нет прав (read/write) ни для одного department_code")

    # Читаем файл
    contents = await file.read()
    try:
        df = pd.read_excel(
            io.BytesIO(contents),
            dtype={
                "Название": str,
                "Инвентарный номер": str,
                "Серийный номер": str,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения Excel файла: {str(e)}")

    # Проверяем наличие обязательных колонок
    required_columns = {"Название", "Инвентарный номер", "Серийный номер", "Количество"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"В файле отсутствуют обязательные колонки: {missing_columns}"
        )

    # Обрабатываем каждую строку
    results = []
    for index, row in df.iterrows():
        excel_row = row.to_dict()

        # Извлекаем основные поля для включения в ответ (для наглядности и отладки)
        name = normalize(excel_row.get("Название"))
        inv_id = normalize(excel_row.get("Инвентарный номер"))
        sn = normalize(excel_row.get("Серийный номер"))

        try:
            result = await process_excel_row(
                excel_row=excel_row,
                db=db,
                allowed_cost_centers=allowed_cost_centers,
                employee_id=current_user.employee_id
            )

            # Расширяем тело ответа полезными данными из строки
            results.append({
                "row": index + 2,
                "inventory_id": inv_id,
                "serial_number": sn,
                "name": name,
                **result  # Сюда распакуется status, asset_id или reason
            })

        except Exception as e:
            await db.rollback()
            logger.error(f"Ошибка при обработке строки {index + 2}: {e}", exc_info=True)
            results.append({
                "row": index + 2,
                "inventory_id": inv_id,
                "serial_number": sn,
                "name": name,
                "status": "error",
                "reason": str(e)
            })

    return {
        "allowed_cost_centers_used": allowed_cost_centers,
        "total_rows": len(df),
        "results": results
    }

@router_excel_import.get("/import-template")
async def get_import_template():
    """Генерирует и отдает Excel-шаблон с примером заполнения под новый формат."""
    columns = [
        "name", "inventory_id", "serial_number", "quantity",
        "comment", "date_issue", "date_purchasing",
        "next_service", "service_period", "check_period"
    ]

    example_data = [
        {
            "name": "Ноутбук Dell Latitude 5520",
            "inventory_id": "0088",
            "serial_number": "SN987654321",
            "quantity": 1,
            "comment": "Выдан сотруднику отдела разработки",
            "date_issue": "2023-10-01",
            "date_purchasing": "2023-09-15",
            "next_service": "2024-10-01",
            "service_period": 365,
            "check_period": 30
        }
    ]

    df = pd.DataFrame(example_data, columns=columns)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Шаблон импорта")

    excel_bytes = output.getvalue()

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=asset_import_template.xlsx"}
    )