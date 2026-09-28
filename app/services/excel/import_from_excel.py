import io
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
import pandas as pd
import httpx

from app.database.connection import get_db
from app.models.assets.Asset import Asset

logger = logging.getLogger(__name__)

router_excel_import = APIRouter(prefix="/excel/assets", tags=["Assets"])

SAP_API_URL = "http://10.168.143.7:8123/sap/base_materials"

# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================
def normalize(value: Any) -> Optional[str]:
    """
    Нормализация: убирает пробелы, приводит к верхнему регистру,
    пустоту и pandas 'nan' превращает в None.
    """
    if value is None:
        return None

    val_str = str(value).strip()

    # Защита от того, что pandas при dtype=str превращает пустые ячейки в строку "nan"
    if val_str == "" or val_str.lower() == "nan":
        return None

    return val_str.upper()


def parse_cost_centers(code_str: Optional[str]) -> List[str]:
    """Разбивает строку cost_center_code на список по разделителю ';'"""
    if not code_str:
        return []
    return [code.strip() for code in str(code_str).split(';') if code.strip()]


async def get_user_cost_center_code(token: str) -> Optional[str]:
    """
    Получает department_code (cost_center_code_from) из API пользователя,
    где у пользователя есть права read и write.
    """
    url = "http://gps-test.hmmr.ru/api/getinfouser"

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(url, json={"token": token})
        response.raise_for_status()
        data = response.json()
        logger.error(f"getinfouser: {data=}")
    for perm in data.get("permission_departments", []):
        if perm.get("read") is True and perm.get("write") is True:
            return perm.get("department_code")

    return None


async def fetch_sap_asset_for_import(
        inventory_id: Optional[str],
        serial_number: Optional[str],
        cost_center_codes_from: List[str]
) -> Optional[Dict[str, Any]]:
    """
    Запрос к SAP API для поиска конкретного актива.
    Возвращает первую найденную запись или None.
    """
    params = {
        "limit": 10, # Берем с небольшим запасом, чтобы отфильтровать у себя
        "offset": 0,
    }

    if inventory_id:
        params["inventory_number"] = inventory_id
    if serial_number:
        params["serial_number"] = serial_number

    # Если есть список cost_center_code_from, передаем их в SAP (API может поддерживать множественные значения или мы отфильтруем вручную)
    if cost_center_codes_from:
        # Передаем как есть через точку с запятой, если API это поддерживает,
        # либо первый элемент, если API строгий. Оставим как строку через ';', как в вашем ТЗ.
        params["cost_center_code_from"] = ";".join(cost_center_codes_from)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(SAP_API_URL, params=params)
            response.raise_for_status()
            data = response.json()

            logger.error(f"SAP: {data=}")

            if data.get("success") and "data" in data.get("response", {}):
                sap_items = data["response"]["data"]

                # Дополнительная локальная фильтрация на случай, если SAP вернул лишнее по cost_center
                for item in sap_items:
                    item_cc = item.get("cost_center_code_from")
                    if not cost_center_codes_from or (item_cc and any(cc in item_cc for cc in cost_center_codes_from)):
                        logger.error(f"{item=}")
                        return item

            return None
    except Exception as e:
        logger.error(f"[SAP IMPORT] Ошибка при запросе к SAP API: {e}")
        return None


# ==============================================================================
# ОСНОВНАЯ ЛОГИКА ОБРАБОТКИ СТРОКИ
# ==============================================================================
async def process_excel_row(
        excel_row: Dict[str, Any],
        db: AsyncSession,
        cost_center_codes_from: List[str]
):
    # Извлечение и нормализация полей из Excel
    inv_id = normalize(excel_row.get("inventory_id"))
    sn = normalize(excel_row.get("serial_number"))
    name = normalize(excel_row.get("name"))
    quantity = excel_row.get("quantity")

    # Если нет ни инвентарного, ни серийного номера, строку обрабатывать бессмысленно
    if not inv_id and not sn:
        return {"status": "skipped", "reason": "Нет inventory_id и serial_number"}

    # Поиск в локальной БД по серийному ИЛИ инвентарному номеру
    # Примечание: фильтры cost_center относятся ТОЛЬКО к SAP (согласно комментарию в get_assets_list_with_sap)
    stmt = select(Asset).where(
        or_(
            Asset.inventory_id == inv_id,
            Asset.serial_number == sn
        )
    )
    result = await db.execute(stmt)
    local_asset = result.scalar_one_or_none()

    # Поиск в SAP (только если не нашли в локальной БД, чтобы сэкономить запросы,
    # или если нужно сверить данные. По ТЗ: "сравнивать... с локальной БД и SAP")
    sap_asset = None
    if not local_asset:
        sap_asset = await fetch_sap_asset_for_import(inv_id, sn, cost_center_codes_from)

    # Матрица решений
    if local_asset:
        # Сценарии A и B: Запись есть в локальной БД.
        # Обновляем значения строго из Excel, если они переданы.
        if name:
            local_asset.name = name
        if inv_id:
            local_asset.inventory_id = inv_id
        if sn:
            local_asset.serial_number = sn
        if quantity is not None:
            local_asset.quantity = int(quantity)

        await db.commit()
        await db.refresh(local_asset)
        return {"status": "updated", "asset_id": local_asset.asset_id}

    else:
        # Сценарии C и D: Записи нет в локальной БД. Создаем новую.
        # Приоритет: Excel > SAP > Значения по умолчанию
        base_data = sap_asset if sap_asset else {}

        new_asset = Asset(
            inventory_id=inv_id or base_data.get("inventory_number"),
            serial_number=sn or base_data.get("serial_number"),
            name=name or base_data.get("base_material_name") or "Без имени",
            quantity=int(quantity) if quantity is not None else (int(base_data.get("quantity", 1)) if base_data.get("quantity") else 1),
            material_id=base_data.get("material_id"), # Раскомментируйте, если есть в модели
            every_week_check=False
        )

        db.add(new_asset)
        await db.commit()
        await db.refresh(new_asset)
        return {"status": "created", "asset_id": new_asset.asset_id}


# ENDPOINT импорта Excel
@router_excel_import.post("/import-from-excel")
async def import_from_excel(
        file: UploadFile = File(..., description="Excel файл для импорта"),
        db: AsyncSession = Depends(get_db)
):
    # TODO: В продакшене заменить на Depends(get_current_user_token)
    token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3OTA1NzE4ODgsImV4cCI6MTc5MDYxNTA4OCwibG9naW4iOiJndzA3MDE1MzcwIiwibGFzdF9pcCI6IjEwLjE2OC4xMzUuMzAiLCJsYXN0X3RpbWUiOiIwOTowNzoxNCAyNS4wOS4yMDI2IiwiZGVwYXJ0bWVudCI6IlJEQyIsInBlcm1pc3Npb25zIjpbeyJuYW1lX2dyb3VwIjoiY29tcHV0ZXIiLCJyZWFkIjpmYWxzZSwid3JpdGUiOmZhbHNlfSx7Im5hbWVfZ3JvdXAiOiJtZXNfZXF1aXBtZW50IiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6InN1cHBsaWVzIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6InBvd2VyX2FkYXB0ZXIiLCJyZWFkIjp0cnVlLCJ3cml0ZSI6dHJ1ZX0seyJuYW1lX2dyb3VwIjoiZGF0YV9jb2xsZWN0aW9uX2VxdWlwbWVudCIsInJlYWQiOnRydWUsIndyaXRlIjp0cnVlfSx7Im5hbWVfZ3JvdXAiOiJBY2Nlc3NvcmllcyIsInJlYWQiOnRydWUsIndyaXRlIjp0cnVlfSx7Im5hbWVfZ3JvdXAiOiJuZXR3b3JrX2VxdWlwbWVudCIsInJlYWQiOnRydWUsIndyaXRlIjp0cnVlfSx7Im5hbWVfZ3JvdXAiOiJwcmludGluZ19lcXVpcG1lbnQiLCJyZWFkIjp0cnVlLCJ3cml0ZSI6dHJ1ZX0seyJuYW1lX2dyb3VwIjoic2VydmVyX2hhcmR3YXJlIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6InVzZXJzIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6IkFzc2V0c01VIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6ImFuZHJvaWRfZGF0YSIsInJlYWQiOnRydWUsIndyaXRlIjpmYWxzZX1dLCJhc3NldHNfaXNfYWRtaW4iOnRydWUsInVzZXJfZGF0YSI6eyJlbWFpbCI6IlRpbXVyLk1hbHlzaGV2QGhtbXIucnUiLCJmdWxsbmFtZSI6IlRpbXVyIE1hbHlzaGV2IiwiZGVwYXJ0bWVudCI6IlJEQyIsImRpc3Rpbmd1aXNoZWROYW1lIjoiQ049VGltdXIgTWFseXNoZXYsT1U9U09GVFdBUkUgREVWRUxPUE1FTlQgR1JPVVAgKFNERyksT1U9SU5GT1JNQVRJT04gU1lTVEVNUyBTVVBQT1JUIFNFQ1RJT04gKElTU1MpLE9VPVJ1c3NpYW4gRGlnaXRhbCBDZW50ZXIgKFJEQyksT1U9VXNlcnMsT1U9SE1NUixEQz1sb2NhbCxEQz1obW1yLERDPXJ1IiwiZ3JvdXBzIjpbXX19.zJdsSVxjSiu_zqa0Mb7Rv-EAq1ZkC2pdeFRTdRh_9kY"

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы .xlsx или .xls")

    # 1. Получаем cost_center_code_from пользователя
    user_cost_center = await get_user_cost_center_code(token)
    if not user_cost_center:
        raise HTTPException(status_code=403, detail="У пользователя нет прав (read/write) ни для одного department_code")

    # Преобразуем в список (на случай, если пользователь имеет доступ к нескольким, или для передачи в SAP)
    cost_center_codes_from = parse_cost_centers(user_cost_center)

    # 2. Читаем файл
    contents = await file.read()
    try:
        df = pd.read_excel(
            io.BytesIO(contents),
            dtype={
                "inventory_id": str,
                "serial_number": str,
                "name": str
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения Excel файла: {str(e)}")

    # 3. Проверяем наличие обязательных колонок
    required_columns = {"name", "inventory_id", "serial_number", "quantity"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"В файле отсутствуют обязательные колонки: {missing_columns}"
        )

    # 4. Обрабатываем каждую строку
    results = []
    for index, row in df.iterrows():
        excel_row = row.to_dict()
        try:
            result = await process_excel_row(
                excel_row=excel_row,
                db=db,
                cost_center_codes_from=cost_center_codes_from
            )
            results.append({"row": index + 2, **result}) # index + 2 т.к. 1 - заголовок, 0 - индекс pandas
        except Exception as e:
            await db.rollback()
            logger.error(f"Ошибка при обработке строки {index + 2}: {e}", exc_info=True)
            results.append({"row": index + 2, "status": "error", "reason": str(e)})

    return {
        "cost_center_code_from_used": cost_center_codes_from,
        "total_rows": len(df),
        "results": results
    }

# ГЕНЕРАЦИЯ ШАБЛОНА EXCEL
@router_excel_import.get("/import-template")
async def get_import_template():
    """
    Генерирует и отдает пустой Excel-шаблон с примером заполнения
    для последующего импорта активов.
    """
    # Определяем строго требуемые колонки
    columns = ["name", "inventory_id", "serial_number", "quantity"]

    # Создаем пример данных для наглядности формата (1 строка)
    example_data = [
        {
            "name": "Ноутбук Dell Latitude 5520",
            "inventory_id": "INV-0000123",
            "serial_number": "SN987654321",
            "quantity": 1
        }
    ]

    # Формируем DataFrame
    df = pd.DataFrame(example_data, columns=columns)

    # Записываем в буфер памяти в формате .xlsx
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Шаблон импорта")

    excel_bytes = output.getvalue()

    # Возвращаем файл с правильными заголовками для скачивания
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=asset_import_template.xlsx"
        }
    )