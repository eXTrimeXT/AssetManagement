import logging
import os

import httpx
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.zup.crud_zup_employees import upsert_employee
from app.database.zup.crud_zup_departments import upsert_department
from app.database.zup.crud_zup_managers import upsert_manager

logger = logging.getLogger(__name__)

ZUP_BASE_URL = os.getenv("ZUP_BASE_URL", "")
ZUP_AUTH = (os.getenv("ZUP_LOGIN", ""), os.getenv("ZUP_PASSWORD", ""))


def clean_empty_strings(data: dict) -> dict:
    """Преобразует пустые строки в None"""
    return {k: (None if v == "" else v) for k, v in data.items()}

async def fetch_from_zup(endpoint: str) -> List[Dict[str, Any]]:
    """Получить данные из 1С-ЗУП"""
    url = f"{ZUP_BASE_URL}/{endpoint}"
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(url, auth=ZUP_AUTH, timeout=30.0)
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


async def sync_all_data(db: AsyncSession) -> Dict[str, int]:
    """Универсальный метод для синхронизации всех данных из 1С"""
    stats = {
        "departments": 0,
        # "positions": 0,
        "employees": 0,
        "managers": 0,
        # "assignments": 0,
        # "reports": 0
    }

    try:
        # 1. Синхронизация подразделений
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

        # 2. Синхронизация должностей
        # logger.info("Синхронизация должностей...")
        # positions_data = await fetch_from_zup("positions")
        # for pos in positions_data:
        #     await upsert_position(db, {
        #         "guid": pos["GUID"],
        #         "name": pos["name"],
        #         "name_en": pos.get("name_EN"),
        #         "creation_date": parse_date(pos.get("creationDate")),
        #         "expiration_date": parse_date(pos.get("expirationDate"))
        #     })
        #     stats["positions"] += 1

        # 3. Синхронизация сотрудников
        logger.info("Синхронизация сотрудников...")
        # employees_data = await fetch_from_zup("employees")
        # for emp in employees_data:
        #     await upsert_employee(db, {
        #         "guid": emp["GUID"],
        #         "guid_person": emp.get("GUID_Person"),
        #         "employee_id": emp["employeeId"],
        #         "last_name": emp.get("lastName"),
        #         "first_name": emp.get("firstName"),
        #         "middle_name": emp.get("middleName"),
        #         "last_name_en": emp.get("lastName_EN"),
        #         "first_name_en": emp.get("firstName_EN"),
        #         "middle_name_en": emp.get("middleName_EN"),
        #         "birth_date": parse_date(emp.get("birthDate")),
        #         "employment_date": parse_date(emp.get("employmentDate")),
        #         "dismissal_date": parse_date(emp.get("dismissalDate")),
        #         "phone": emp.get("phone"),
        #         "email": emp.get("email"),
        #         "position_guid": emp.get("position"),
        #         "department_guid": emp.get("department")
        #     })
        #     stats["employees"] += 1

        employees_data = await fetch_from_zup("employees")
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

            # Очищаем пустые строки
            employee_data = clean_empty_strings(employee_data)
        
            await upsert_employee(db, employee_data)
            stats["employees"] += 1

        # 4. Синхронизация руководителей
        logger.info("Синхронизация руководителей...")
        managers_data = await fetch_from_zup("managers")
        for idx, mgr in enumerate(managers_data):
            await upsert_manager(db, {
                "id": f"{mgr['GUID_Employee']}_{mgr['GUID_Manager']}",
                "guid_employee": mgr["GUID_Employee"],
                "guid_manager": mgr["GUID_Manager"]
            })
            stats["managers"] += 1

        # 5. Синхронизация назначений
        # logger.info("Синхронизация назначений...")
        # assignments_data = await fetch_from_zup("assignments")
        # for idx, assign in enumerate(assignments_data):
        #     await upsert_assignment(db, {
        #         "id": f"{assign['employee']}_{assign['startDate']}_{idx}",
        #         "start_date": parse_date(assign["startDate"]),
        #         "end_date": parse_date(assign.get("endDate")),
        #         "employee_guid": assign["employee"],
        #         "department_guid": assign["department"],
        #         "position_guid": assign["position"],
        #         "fte": float(assign.get("fte", "1").replace(",", "."))
        #     })
        #     stats["assignments"] += 1

        # 6. Синхронизация отчётов
        # logger.info("Синхронизация отчётов...")
        # report_data = await fetch_from_zup("report")
        # attendance_data = [
        #     AttendanceData(**item)
        #     for item in report_data.get("attendanceData", [])
        # ]
        # await create_report(db, attendance_data)
        # stats["reports"] = len(attendance_data)

        logger.info(f"Синхронизация завершена: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Ошибка синхронизации: {e}")
        raise