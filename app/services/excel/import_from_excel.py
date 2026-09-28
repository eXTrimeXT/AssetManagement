import io
import httpx
from typing import Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import or_
import pandas as pd

from app.database.connection import get_db
from app.models.assets import Asset

router_excel_import = APIRouter(prefix="/assets", tags=["Assets"])

# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================
def normalize(value: Any) -> Optional[str]:
    """Нормализация: убирает пробелы, приводит к верхнему регистру, пустоту превращает в None"""
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip().upper()


async def get_user_cost_center_code(token: str) -> Optional[str]:
    """
    Получает department_code (cost_center_code_from) из API пользователя,
    где у пользователя есть права read и write.
    """
    url = "http://gps-test.hmmr.ru/api/getinfouser"

    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Cookie": f"PHPSESSID=8s9909705lor036d1bppe54o85; lang=ru; token={token}",
        "DNT": "1",
        "Origin": "http://gps-test.hmmr.ru",
        "Referer": "http://gps-test.hmmr.ru/itassets/Store/10",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
        "X-KL-kes-Ajax-Request": "Ajax_Request",
        "X-Requested-With": "XMLHttpRequest"
    }

    payload = {"token": token}

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(url, headers=headers, data=payload)
        response.raise_for_status()
        data = response.json()

    for perm in data.get("permission_departments", []):
        if perm.get("read") is True and perm.get("write") is True:
            return perm.get("department_code")

    return None


# Заглушка для SAP клиента. Замените на ваш реальный класс/функцию запроса к SAP
class SAPClient:

    async def get_asset(inventory_id: Optional[str], serial_number: Optional[str]) -> Optional[Dict[str, Any]]:
        # TODO: Реализуйте здесь реальный запрос к SAP
        # Пример возврата: {"name": "SAP Name", "quantity": 1, ...}
        return None


sap_client = SAPClient()


# ==============================================================================
# ОСНОВНАЯ ЛОГИКА ОБРАБОТКИ СТРОКИ
# ==============================================================================

async def process_excel_row(
        excel_row: Dict[str, Any],
        db: Session,
        cost_center_code: Optional[str]
):
    # 1. Извлечение и нормализация полей из Excel
    inv_id = normalize(excel_row.get("inventory_id"))
    sn = normalize(excel_row.get("serial_number"))
    name = normalize(excel_row.get("name"))
    quantity = excel_row.get("quantity")

    # Если нет ни инвентарного, ни серийного номера, строку обрабатывать бессмысленно
    if not inv_id and not sn:
        return {"status": "skipped", "reason": "Нет inventory_id и serial_number"}

    # 2. Поиск в локальной БД по серийному ИЛИ инвентарному номеру
    # Добавляем фильтрацию по cost_center_code, если он передан и существует в модели
    query = db.query(Asset).filter(
        or_(
            Asset.inventory_id == inv_id,
            Asset.serial_number == sn
        )
    )

    # Если в вашей модели Asset есть поле cost_center_code, раскомментируйте следующую строку:
    if cost_center_code:
        query = query.filter(Asset.cost_center_code == cost_center_code)

    local_asset = query.first()

    # 3. Поиск в SAP
    sap_asset = await sap_client.get_asset(inventory_id=inv_id, serial_number=sn)

    # 4. Матрица решений
    if local_asset:
        # Сценарии A и B: Запись есть в локальной БД.
        # Дополняем её значениями из Excel, если поля пустые (или перезаписываем, если ТЗ требует строго значения из Excel)
        # Согласно ТЗ: "всегда должен создавать/обновляться актив в локальную БД, со значениями из excel!"
        if name:
            local_asset.name = name
        if inv_id:
            local_asset.inventory_id = inv_id
        if sn:
            local_asset.serial_number = sn
        if quantity is not None:
            local_asset.quantity = int(quantity)

        db.commit()
        db.refresh(local_asset)
        return {"status": "updated", "asset_id": local_asset.asset_id}

    else:
        # Сценарии C и D: Записи нет в локальной БД. Создаем новую.
        # Берем данные из SAP как базу (если есть), но значения из Excel имеют высший приоритет.
        base_data = sap_asset if sap_asset else {}

        new_asset = Asset(
            inventory_id=inv_id or base_data.get("inventory_id"),
            serial_number=sn or base_data.get("serial_number"),
            name=name or base_data.get("name") or "Без имени",
            quantity=int(quantity) if quantity is not None else base_data.get("quantity", 1),
            # Если в модели есть cost_center_code, сохраняем контекст пользователя:
            # cost_center_code=cost_center_code,
        )

        db.add(new_asset)
        db.commit()
        db.refresh(new_asset)
        return {"status": "created", "asset_id": new_asset.asset_id}


# ==============================================================================
# FASTAPI ENDPOINT
# ==============================================================================

@router_excel_import.post("/import-from-excel")
async def import_from_excel(
        file: UploadFile = File(..., description="Excel файл для импорта"),
        # token: str = Depends(get_current_user_token),
        db: AsyncSession = Depends(get_db)
):
    token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3OTA1NzE4ODgsImV4cCI6MTc5MDYxNTA4OCwibG9naW4iOiJndzA3MDE1MzcwIiwibGFzdF9pcCI6IjEwLjE2OC4xMzUuMzAiLCJsYXN0X3RpbWUiOiIwOTowNzoxNCAyNS4wOS4yMDI2IiwiZGVwYXJ0bWVudCI6IlJEQyIsInBlcm1pc3Npb25zIjpbeyJuYW1lX2dyb3VwIjoiY29tcHV0ZXIiLCJyZWFkIjpmYWxzZSwid3JpdGUiOmZhbHNlfSx7Im5hbWVfZ3JvdXAiOiJtZXNfZXF1aXBtZW50IiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6InN1cHBsaWVzIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6InBvd2VyX2FkYXB0ZXIiLCJyZWFkIjp0cnVlLCJ3cml0ZSI6dHJ1ZX0seyJuYW1lX2dyb3VwIjoiZGF0YV9jb2xsZWN0aW9uX2VxdWlwbWVudCIsInJlYWQiOnRydWUsIndyaXRlIjp0cnVlfSx7Im5hbWVfZ3JvdXAiOiJBY2Nlc3NvcmllcyIsInJlYWQiOnRydWUsIndyaXRlIjp0cnVlfSx7Im5hbWVfZ3JvdXAiOiJuZXR3b3JrX2VxdWlwbWVudCIsInJlYWQiOnRydWUsIndyaXRlIjp0cnVlfSx7Im5hbWVfZ3JvdXAiOiJwcmludGluZ19lcXVpcG1lbnQiLCJyZWFkIjp0cnVlLCJ3cml0ZSI6dHJ1ZX0seyJuYW1lX2dyb3VwIjoic2VydmVyX2hhcmR3YXJlIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6InVzZXJzIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6IkFzc2V0c01VIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6ImFuZHJvaWRfZGF0YSIsInJlYWQiOnRydWUsIndyaXRlIjpmYWxzZX1dLCJhc3NldHNfaXNfYWRtaW4iOnRydWUsInVzZXJfZGF0YSI6eyJlbWFpbCI6IlRpbXVyLk1hbHlzaGV2QGhtbXIucnUiLCJmdWxsbmFtZSI6IlRpbXVyIE1hbHlzaGV2IiwiZGVwYXJ0bWVudCI6IlJEQyIsImRpc3Rpbmd1aXNoZWROYW1lIjoiQ049VGltdXIgTWFseXNoZXYsT1U9U09GVFdBUkUgREVWRUxPUE1FTlQgR1JPVVAgKFNERyksT1U9SU5GT1JNQVRJT04gU1lTVEVNUyBTVVBQT1JUIFNFQ1RJT04gKElTU1MpLE9VPVJ1c3NpYW4gRGlnaXRhbCBDZW50ZXIgKFJEQyksT1U9VXNlcnMsT1U9SE1NUixEQz1sb2NhbCxEQz1obW1yLERDPXJ1IiwiZ3JvdXBzIjpbXX19.zJdsSVxjSiu_zqa0Mb7Rv-EAq1ZkC2pdeFRTdRh_9kY"

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы .xlsx или .xls")

    # 1. Получаем cost_center_code_from пользователя
    cost_center_code = await get_user_cost_center_code(token)
    if not cost_center_code:
        raise HTTPException(status_code=403, detail="У пользователя нет прав (read/write) ни для одного department_code")

    # 2. Читаем файл
    contents = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения Excel файла: {str(e)}")

    # 3. Проверяем наличие обязательных колонок
    required_columns = {"name", "inventory_id", "serial_number", "quantity"}
    if not required_columns.issubset(df.columns):
        raise HTTPException(
            status_code=400,
            detail=f"В файле отсутствуют обязательные колонки: {required_columns - set(df.columns)}"
        )

    # 4. Обрабатываем каждую строку
    results = []
    for index, row in df.iterrows():
        excel_row = row.to_dict()
        try:
            result = await process_excel_row(
                excel_row=excel_row,
                db=db,
                cost_center_code=cost_center_code
            )
            results.append({"row": index + 2, **result}) # index + 2 т.к. 1 - заголовок, 0 - индекс
        except Exception as e:
            db.rollback()
            results.append({"row": index + 2, "status": "error", "reason": str(e)})

    return {
        "cost_center_code": cost_center_code,
        "total_rows": len(df),
        "results": results
    }