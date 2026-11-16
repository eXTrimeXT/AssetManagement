import logging
import uuid
import os
from datetime import date, datetime
from typing import List, Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)

# Берём из переменных окружения или используем дефолтные (как в твоем рабочем примере)
SAP_CHANGE_FA_URL = os.getenv("SAP_CHANGE_FA_URL", "http://sap-qas-app.hmmr.ru:60000/sap/opu/odata/sap/ZCHANGE_FA_ALL_INFORM_SRV/HeaderSet")
SAP_AUTH_HEADER = os.getenv("SAP_AUTH_HEADER", "Basic TOKEN")

# Маппинг полей локальной модели Asset на FieldName в SAP (согласно спецификации)
LOCAL_TO_SAP_FIELD_MAPPING = {
    "name": "DESCRIPT",
    "inventory_id": "INVENT_NO",
    "serial_number": "SERIAL_NUM_LONG",
    "quantity": "QUANTITY",
    "comment": "MAIN_DESCRIPT",
    "date_purchasing": "ORIG_ACQ_DATE",  # Пример: дата покупки -> дата поступления
    # "date_issue": "DATE",              # Пример: дата выдачи -> дата инвентаризации
    "manufacturer_name": "MANUFACTURER",
    "vendor_name": "VENDOR_NO",
    "cost_center_code_from": "RESP_CCTR",
    "cost_center_code": "COSTCENTER",
    "current_user": "PERSON_NO",
}

#     "date_issue": null,
#     "date_purchasing": null,
#     "location": null,
#     "users": [],
#     "material_class": null,
#     "write_off_date": null,
#     "material_class_name": null


def _format_sap_value(field_name: str, value: Any) -> str:
    """Форматирует значение для отправки в SAP согласно правилам спецификации."""
    if value is None:
        return ""

    # Преобразование дат в YYYYMMDD
    if field_name in ("ORIG_ACQ_DATE", "DATE", "FROM_DATE") or isinstance(value, (date, datetime)):
        if isinstance(value, (date, datetime)):
            return value.strftime("%Y%m%d")
        return str(value).strip()

    # Для числовых и строковых значений
    return str(value).strip()


def build_sap_item_set_from_changes(old_data: Dict[str, Any], new_data: Dict[str, Any], req_id: str) -> List[Dict[str, Any]]:
    """
    Сравнивает old_data и new_data, находит изменения и формирует ItemSet для SAP.
    Передаются только те поля, которые реально изменились.
    """
    # Поля, которые согласно ТЗ должны передаваться вместе с FROM_DATE
    TIME_DEPENDENT_FIELDS = {
        "COSTCENTER", "RESP_CCTR", "INTERN_ORD", "PLANT",
        "LOCATION", "ROOM", "PLATE_NO", "PERSON_NO", "SHUTDOWN"
    }

    item_set = []
    has_time_fields = False
    has_from_date = False

    # === ШАГ 1: Собираем все изменения ===
    for key, new_val in new_data.items():
        old_val = old_data.get(key)

        # Если значение не изменилось, пропускаем (п.1 ТЗ)
        if old_val == new_val:
            continue

        # Проверяем, есть ли маппинг для этого локального поля
        sap_field_name = LOCAL_TO_SAP_FIELD_MAPPING.get(key)
        if not sap_field_name:
            logger.debug(f"[SAP FA CHANGE] Поле '{key}' не имеет маппинга в SAP, пропускаем.")
            continue

        formatted_value = _format_sap_value(sap_field_name, new_val)

        # Отслеживаем наличие временных полей и FROM_DATE
        if sap_field_name in TIME_DEPENDENT_FIELDS:
            has_time_fields = True
        if sap_field_name == "FROM_DATE":
            has_from_date = True

        item_set.append({
            "FieldName": sap_field_name,
            "FieldValue": formatted_value
        })

    # === ШАГ 2: Если есть временные поля, но нет FROM_DATE — добавляем текущую дату сервера ===
    # (Согласно ТЗ п.6: "при изменении временных данных без даты предполагается SY-DATUM")
    if has_time_fields and not has_from_date:
        from datetime import date
        today_str = date.today().strftime("%Y%m%d")
        item_set.append({
            "FieldName": "FROM_DATE",
            "FieldValue": today_str
        })
        logger.info(f"[SAP FA CHANGE] Автоматически добавлен FROM_DATE={today_str} (SY-DATUM)")

    # === ШАГ 3: Проставляем последовательные ReqID и ItemNo ===
    for idx, item in enumerate(item_set, start=1):
        item["ReqID"] = req_id
        item["ItemNo"] = idx

    return item_set

def format_asset_number(asset_number: str) -> str:
    if not asset_number:
        raise ValueError("AssetNumber (номер основного средства) обязателен")
    if len(asset_number) == 12:
        return asset_number
    elif len(asset_number) > 12:
        return asset_number[:12]
    return str(asset_number).strip().zfill(12)


async def change_fixed_asset(
        asset_number: str,
        item_set: List[Dict[str, Any]],
        req_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not item_set:
        logger.info("[SAP FA CHANGE] Изменений для отправки в SAP нет. Пропуск.")
        return {"success": True, "message": "No changes to sync"}

    company_code = "RU00"
    sub_number = "0000"

    formatted_asset_number = format_asset_number(asset_number)
    request_id = req_id or f"REQ-{uuid.uuid4().hex[:8].upper()}"

    payload = {
        "ReqID": request_id,
        "CompanyCode": company_code,
        "AssetNumber": formatted_asset_number,
        "SubNumber": sub_number,
        "ItemSet": item_set
    }

    logger.info(f"[SAP FA CHANGE] Начало процесса изменения ОС {formatted_asset_number}, ReqID: {request_id}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Шаг 1: Получение X-CSRF-Token
        fetch_headers = {
            "X-CSRF-Token": "Fetch",
            "Accept": "application/json",
            "Authorization": SAP_AUTH_HEADER,
            "sap-client": "800"
        }
        fetch_response = await client.get(SAP_CHANGE_FA_URL, headers=fetch_headers)
        csrf_token = fetch_response.headers.get("x-csrf-token")

        if not csrf_token or csrf_token.lower() == "required":
            logger.error(f"[SAP FA CHANGE] Не удалось получить X-CSRF-Token. Статус: {fetch_response.status_code}")
            raise ValueError(f"Не удалось получить X-CSRF-Token. Статус: {fetch_response.status_code}")

        # Шаг 2: POST-запрос на изменение
        post_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-CSRF-Token": csrf_token,
            "Authorization": SAP_AUTH_HEADER,
            "sap-client": "800"
        }

        response = await client.post(SAP_CHANGE_FA_URL, json=payload, headers=post_headers)

        if response.status_code >= 400:
            error_detail = response.text
            logger.error(f"[SAP FA CHANGE] Ошибка при изменении ОС: {response.status_code}")
            try:
                error_json = response.json()
                error_msg = error_json.get("error", {}).get("message", {}).get("value", error_detail)
                raise ValueError(f"SAP API Error: {error_msg}")
            except Exception:
                raise ValueError(f"SAP API Error: HTTP {response.status_code} - {error_detail[:300]}")

        logger.info("[SAP FA CHANGE] ОС успешно изменено в SAP!")
        return response.json()


# Удобная обёртка для вызова из CRUD
async def sync_asset_changes_to_sap(asset_number: str, old_data: Dict[str, Any], new_data: Dict[str, Any], req_id: Optional[str] = None):
    item_set = build_sap_item_set_from_changes(old_data, new_data, req_id or f"SYNC-{uuid.uuid4().hex[:6].upper()}")
    if item_set:
        return await change_fixed_asset(asset_number, item_set, req_id)
    return None