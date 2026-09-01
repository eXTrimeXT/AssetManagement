import logging
import os

import httpx
from typing import List, Dict, Any

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from sqlalchemy.ext.asyncio import AsyncSession
from app.database.zup.crud_zup_employees import upsert_employee, bulk_upsert_employees
from app.database.zup.crud_zup_departments import upsert_department
from app.database.zup.crud_zup_positions import upsert_position

logger = logging.getLogger(__name__)

ZUP_BASE_URL = os.getenv("ZUP_BASE_URL", "")
ZUP_AUTH = (os.getenv("ZUP_LOGIN", ""), os.getenv("ZUP_PASSWORD", ""))

# Глобальный клиент с пулом соединений
_http_client: httpx.AsyncClient | None = None

def get_http_client():
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            verify=False,
            timeout=30.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
    return _http_client

async def close_http_client():
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None

def clean_empty_strings(data: dict) -> dict:
    """Преобразует пустые строки в None"""
    return {k: (None if v == "" else v) for k, v in data.items()}

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)),
    reraise=True
)
async def fetch_from_zup(endpoint: str) -> List[Dict[str, Any]]:
    """Получить данные из 1С-ЗУП с повторными попытками, """
    url = f"{ZUP_BASE_URL}/{endpoint}"
    client = get_http_client()
    try:
        response = await client.get(url, auth=ZUP_AUTH)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Ошибка при запросе к 1С-ЗУП {endpoint}: {e}")
        raise

def parse_date(date_str: str):
    """Парсить дату из формата DD.MM.YYYY"""
    if not date_str or date_str == "":
        return None
    try:
        from datetime import datetime
        return datetime.strptime(date_str, "%d.%m.%Y").date()
    except Exception:
        return None

async def sync_employee_data(db: AsyncSession) -> Dict[str, int]:
    stats = {
        "employees": 0,
    }

    logger.info("Синхронизация сотрудников...")
    employees_data = await fetch_from_zup("employees")
    for emp in employees_data:
        await upsert_employee(db, {
            "guid": emp["GUID"],
            "guid_person": emp.get("GUID_Person"),
            "employee_id": emp["employeeId"],
            "last_name": emp.get("lastName"),
            "first_name": emp.get("firstName"),
            "middle_name": emp.get("middleName"),
            "last_name_en": emp.get("lastName_EN"),
            "first_name_en": emp.get("firstName_EN"),
            "middle_name_en": emp.get("middleName_EN"),
            "birth_date": parse_date(emp.get("birthDate")),
            "employment_date": parse_date(emp.get("employmentDate")),
            "dismissal_date": parse_date(emp.get("dismissalDate")),
            "phone": emp.get("phone"),
            "email": emp.get("email"),
            "position_guid": emp.get("position"),
            "department_guid": emp.get("department")
        })
        stats["employees"] += 1
    return stats

async def sync_all_data(db: AsyncSession) -> Dict[str, int]:
    """Универсальный метод для синхронизации всех данных из 1С"""
    stats = {
        "departments": 0,
        "positions": 0,
        "employees": 0,
        "managers": 0,
    }

    try:
        # Синхронизация подразделений
        logger.info("Синхронизация подразделений...")
        departments_data = await fetch_from_zup("departments")
        for dept in departments_data:
            await upsert_department(db, {
                "guid": dept["GUID"],
                "name": dept["name"],
                "name_en": dept.get("name_EN"),
                "short_name": dept.get("shortName"),
                "creation_date": parse_date(dept.get("creationDate")),
                "closure_date": parse_date(dept.get("closureDate")),
                "parent_guid": dept.get("parent") if dept.get("parent") else None
            })
            stats["departments"] += 1

        # Синхронизация должностей
        logger.info("Синхронизация должностей...")
        positions_data = await fetch_from_zup("positions")
        for pos in positions_data:
            await upsert_position(db, {
                "guid": pos["GUID"],
                "name": pos["name"],
                "name_en": pos.get("name_EN"),
                "creation_date": parse_date(pos.get("creationDate")),
                "expiration_date": parse_date(pos.get("expirationDate"))
            })
            stats["positions"] += 1

        # Синхронизация сотрудников
        logger.info("Синхронизация сотрудников...")
        employees_data = await fetch_from_zup("employees")
        employees_to_upsert = []

        for emp in employees_data:
            employee_data = {
                "guid": emp["GUID"],
                "guid_person": emp.get("GUID_Person"),
                "employee_id": emp["employeeId"],
                "last_name": emp.get("lastName"),
                "first_name": emp.get("firstName"),
                "middle_name": emp.get("middleName"),
                "last_name_en": emp.get("lastName_EN"),
                "first_name_en": emp.get("firstName_EN"),
                "middle_name_en": emp.get("middleName_EN"),
                "birth_date": parse_date(emp.get("birthDate")),
                "employment_date": parse_date(emp.get("employmentDate")),
                "dismissal_date": parse_date(emp.get("dismissalDate")),
                "phone": emp.get("phone"),
                "email": emp.get("email"),
                "position_guid": emp.get("position"),
                "department_guid": emp.get("department")
            }
            employees_to_upsert.append(clean_empty_strings(employee_data))

        # Выполняем пакетную загрузку с защитой от лимита параметров
        stats["employees"] = await bulk_upsert_employees(db, employees_to_upsert)

        # Синхронизация руководителей
        # logger.info("Синхронизация руководителей...")
        # managers_data = await fetch_from_zup("managers")
        # for idx, mgr in enumerate(managers_data):
        #     await upsert_manager(db, {
        #         "id": f"{mgr['GUID_Employee']}_{mgr['GUID_Manager']}",
        #         "guid_employee": mgr["GUID_Employee"],
        #         "guid_manager": mgr["GUID_Manager"]
        #     })
        #     stats["managers"] += 1

        logger.info(f"Синхронизация завершена: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Ошибка синхронизации: {e}")
        raise