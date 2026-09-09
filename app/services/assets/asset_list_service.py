import hashlib
import logging
import zlib
from typing import List, Dict, Optional, Any, Sequence
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import httpx

from app.models.assets.Asset import Asset
from app.models.assets.AssetAssignment import AssetAssignment
from app.models.assets.AssetStatus import AssetStatus
from app.models.map_assets.AssetPosition import AssetPosition
from app.models.zup.employee import Employee
from app.models.zup.department import ZupDepartment

logger = logging.getLogger(__name__)

SAP_API_URL = "http://10.168.143.7:8123/sap/base_materials"


# async def get_assets_list_with_sap(
#         db: AsyncSession,
#         page: int = 1,
#         page_size: int = 50,
#         name: Optional[str] = None,
#         inventory_id: Optional[str] = None,
#         serial_number: Optional[str] = None,
#         asset_status: Optional[str] = None,
#         model_id: Optional[int] = None,
#         asset_type_id: Optional[int] = None,
#         parent_id: Optional[int] = None,
#         search_mode: str = "not_nulls",
#         employee_id: Optional[str] = None,
# ) -> Dict[str, Any]:
#     """
#     Получение списка активов с слиянием данных из SAP API и локальной БД.
#     При ошибке SAP API — возвращаются только локальные данные.
#     """
#
#     # Шаг 1: Попытка получить данные из SAP API
#     sap_items = None
#     sap_total = None
#     try:
#         sap_response = await _fetch_sap_materials(
#             page=page,
#             page_size=page_size,
#             search_mode=search_mode,
#             base_material_name_like=name,
#             inventory_number=inventory_id,
#             serial_number=serial_number,
#             employee_id=employee_id,
#         )
#
#         if not sap_response.get("success") or "response" not in sap_response or "data" not in sap_response["response"]:
#             logger.error(f"[SAP FALLBACK] Неверная структура ответа SAP API: {sap_response}")
#             raise ValueError("Неверная структура ответа SAP API")
#
#         sap_data = sap_response.get("response", {})
#         sap_items = sap_data.get("data", [])
#         sap_total = sap_data.get("total", 0)
#         logger.info(f"[SAP] Получено {len(sap_items)} записей из SAP API")
#
#     except Exception as e:
#         logger.error(f"[SAP FALLBACK] Ошибка при запросе к SAP API, переключаемся на локальные данные: {e}", exc_info=True)
#         sap_items = None
#         sap_total = None
#
#     # Шаг 2: Если SAP упал — возвращаем только локальные данные
#     if sap_items is None:
#         return await _get_local_assets_only(
#             db=db,
#             page=page,
#             page_size=page_size,
#             name=name,
#             inventory_id=inventory_id,
#             serial_number=serial_number,
#             asset_status=asset_status,
#             model_id=model_id,
#             asset_type_id=asset_type_id,
#             parent_id=parent_id,
#             employee_id=employee_id,
#         )
#
#     # Шаг 3: Если SAP вернул пустой список
#     if not sap_items:
#         return _build_paginated_response([], sap_total, page, page_size)
#
#     # Шаг 4: Массовая загрузка локальных активов по material_id
#     material_ids = [item["material_id"] for item in sap_items if item.get("material_id")]
#     local_assets = await _get_local_assets_by_material_ids(db, material_ids)
#     local_assets_map = {asset.material_id: asset for asset in local_assets}
#
#     # Шаг 5: Массовая загрузка сотрудников и департаментов
#     employee_ids = set()
#     department_codes = set()
#     for item in sap_items:
#         if item.get("employee_id"):
#             employee_ids.add(item["employee_id"])
#         if item.get("department_code"):
#             department_codes.add(item["department_code"])
#
#     employees_map = {}
#     if employee_ids:
#         employees = await _get_employees_by_ids(db, list(employee_ids))
#         employees_map = {emp.employee_id: emp for emp in employees}
#
#     departments_map = {}
#     if department_codes:
#         departments = await _get_departments_by_codes(db, list(department_codes))
#         departments_map = {dept.short_name: dept for dept in departments}
#
#     # Шаг 6: Слияние данных
#     result_items = []
#     for sap_item in sap_items:
#         material_id = sap_item.get("material_id")
#
#         if material_id in local_assets_map:
#             result_items.append(local_assets_map[material_id])
#         else:
#             virtual_asset = _build_virtual_asset(sap_item, employees_map, departments_map)
#             result_items.append(virtual_asset)
#
#     # Шаг 7: Применяем "локальные" фильтры постфактум
#     has_local_filters = any([
#         asset_status is not None,
#         model_id is not None,
#         asset_type_id is not None,
#         parent_id is not None,
#         ])
#     if has_local_filters:
#         result_items = _apply_local_filters(
#             result_items, asset_status, model_id, asset_type_id, parent_id
#         )
#
#     return _build_paginated_response(result_items, sap_total, page, page_size)


async def get_assets_list_with_sap(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 50,
        name: Optional[str] = None,
        inventory_id: Optional[str] = None,
        serial_number: Optional[str] = None,
        asset_status: Optional[str] = None,
        model_id: Optional[int] = None,
        asset_type_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        employee_id: Optional[str] = None,
        search_mode: str = "not_nulls",
) -> Dict[str, Any]:
    """
    Получение списка активов с слиянием данных из SAP API и локальной БД.
    """

    # Проверяем, есть ли фильтры, которые существуют ТОЛЬКО в локальной БД
    has_local_only_filters = any([
        asset_status is not None,
        model_id is not None,
        asset_type_id is not None,
        parent_id is not None,
        ])

    # Если есть локальные фильтры, виртуальные активы из SAP всё равно не подойдут
    # (у них эти поля равны None). Поэтому сразу идём в локальную БД.
    # Это решает проблему пустых страниц при фильтрации по типу, модели и т.д.
    if has_local_only_filters:
        logger.info(f"[LOCAL FILTER] Обнаружен локальный фильтр (asset_type_id={asset_type_id}, model_id={model_id}), запрос идёт напрямую в БД.")
        return await _get_local_assets_only(
            db=db,
            page=page,
            page_size=page_size,
            name=name,
            inventory_id=inventory_id,
            serial_number=serial_number,
            asset_status=asset_status,
            model_id=model_id,
            asset_type_id=asset_type_id,
            parent_id=parent_id,
            employee_id=employee_id,
        )

    # Если локальных фильтров нет, работаем по стандартной схеме с SAP API
    sap_items = None
    sap_total = None
    try:
        sap_response = await _fetch_sap_materials(
            page=page,
            page_size=page_size,
            search_mode=search_mode,
            base_material_name_like=name,
            inventory_number=inventory_id,
            serial_number=serial_number,
            employee_id=employee_id,
        )

        if not sap_response.get("success") or "response" not in sap_response or "data" not in sap_response["response"]:
            logger.error(f"[SAP FALLBACK] Неверная структура ответа SAP API: {sap_response}")
            raise ValueError("Неверная структура ответа SAP API")

        sap_data = sap_response.get("response", {})
        sap_items = sap_data.get("data", [])
        sap_total = sap_data.get("total", 0)
        logger.info(f"[SAP] Получено {len(sap_items)} записей из SAP API")

    except Exception as e:
        logger.error(f"[SAP FALLBACK] Ошибка при запросе к SAP API, переключаемся на локальные данные: {e}", exc_info=True)
        sap_items = None
        sap_total = None

    # Если SAP упал — возвращаем только локальные данные
    if sap_items is None:
        return await _get_local_assets_only(
            db=db,
            page=page,
            page_size=page_size,
            name=name,
            inventory_id=inventory_id,
            serial_number=serial_number,
            asset_status=asset_status,
            model_id=model_id,
            asset_type_id=asset_type_id,
            parent_id=parent_id,
            employee_id=employee_id,
        )

    # Если SAP вернул пустой список
    if not sap_items:
        return _build_paginated_response([], sap_total, page, page_size)

    # Массовая загрузка локальных активов по material_id
    material_ids = [item["material_id"] for item in sap_items if item.get("material_id")]
    local_assets = await _get_local_assets_by_material_ids(db, material_ids)
    local_assets_map = {asset.material_id: asset for asset in local_assets}

    # Массовая загрузка сотрудников и департаментов
    employee_ids = set()
    department_codes = set()
    for item in sap_items:
        if item.get("employee_id"):
            employee_ids.add(item["employee_id"])
        if item.get("department_code"):
            department_codes.add(item["department_code"])

    employees_map = {}
    if employee_ids:
        employees = await _get_employees_by_ids(db, list(employee_ids))
        employees_map = {emp.employee_id: emp for emp in employees}

    departments_map = {}
    if department_codes:
        departments = await _get_departments_by_codes(db, list(department_codes))
        departments_map = {dept.short_name: dept for dept in departments}

    # Слияние данных
    result_items = []
    for sap_item in sap_items:
        material_id = sap_item.get("material_id")

        if material_id in local_assets_map:
            result_items.append(local_assets_map[material_id])
        else:
            virtual_asset = _build_virtual_asset(sap_item, employees_map, departments_map)
            result_items.append(virtual_asset)

    return _build_paginated_response(result_items, sap_total, page, page_size)

async def _get_local_assets_only(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 50,
        name: Optional[str] = None,
        inventory_id: Optional[str] = None,
        serial_number: Optional[str] = None,
        asset_status: Optional[str] = None,
        model_id: Optional[int] = None,
        asset_type_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        employee_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Резервный режим: SAP недоступен, возвращаем только локальные активы.
    Все фильтры применяются на стороне БД.
    """
    logger.info("[SAP FALLBACK] Загрузка только локальных активов из БД")

    # Строим базовый запрос
    base_query = select(Asset).options(
        selectinload(Asset.asset_type),
        selectinload(Asset.asset_status),
        selectinload(Asset.model),
        selectinload(Asset.parent).options(
            selectinload(Asset.asset_type),
            selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
        ),
        selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
        selectinload(Asset.assignments).options(
            selectinload(AssetAssignment.employee)
        ),
    )

    # Применяем все фильтры
    if name:
        base_query = base_query.where(Asset.name.ilike(f"%{name}%"))
    if inventory_id:
        base_query = base_query.where(Asset.inventory_id.ilike(f"%{inventory_id}%"))
    if serial_number:
        base_query = base_query.where(Asset.serial_number.ilike(f"%{serial_number}%"))
    if model_id is not None:
        base_query = base_query.where(Asset.model_id == model_id)
    if asset_type_id is not None:
        base_query = base_query.where(Asset.asset_type_id == asset_type_id)
    if parent_id is not None:
        base_query = base_query.where(Asset.parent_id == parent_id)
    if asset_status:
        base_query = base_query.join(AssetStatus, Asset.asset_status_id == AssetStatus.id)
        base_query = base_query.where(AssetStatus.status == asset_status)
    if employee_id:
        emp_asset_subq = (
            select(AssetAssignment.asset_id)
            .where(AssetAssignment.employee_id == employee_id)
            .scalar_subquery()
        )
        base_query = base_query.where(Asset.asset_id.in_(emp_asset_subq))

    # Считаем total
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Пагинация
    skip = (page - 1) * page_size
    items_query = base_query.order_by(Asset.asset_id).offset(skip).limit(page_size)
    result = await db.execute(items_query)
    items = result.scalars().all()

    return _build_paginated_response(list(items), total, page, page_size)


def _apply_local_filters(
        items: List[Any],
        asset_status: Optional[str],
        model_id: Optional[int],
        asset_type_id: Optional[int],
        parent_id: Optional[int],
) -> List[Any]:
    """Применяет фильтры, которые существуют только в локальной БД."""
    filtered = []
    for item in items:
        if isinstance(item, dict):
            item_status = item.get("asset_status")
            item_model_id = item.get("model_id")
            item_asset_type_id = item.get("asset_type_id")
            item_parent_id = item.get("parent_id")
        else:
            item_status = item.asset_status.status if item.asset_status else None
            item_model_id = item.model_id
            item_asset_type_id = item.asset_type_id
            item_parent_id = item.parent_id

        if asset_status is not None and item_status != asset_status:
            continue
        if model_id is not None and item_model_id != model_id:
            continue
        if asset_type_id is not None and item_asset_type_id != asset_type_id:
            continue
        if parent_id is not None and item_parent_id != parent_id:
            continue

        filtered.append(item)

    return filtered


def _build_paginated_response(
        items: List[Any], total: int, page: int, page_size: int
) -> Dict[str, Any]:
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


async def _fetch_sap_materials(
        page: int,
        page_size: int,
        search_mode: str = "not_nulls",
        base_material_name_like: Optional[str] = None,
        inventory_number: Optional[str] = None,
        serial_number: Optional[str] = None,
        employee_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Запрос к SAP API для получения списка материалов."""
    offset = (page - 1) * page_size

    params = {
        "limit": page_size,
        "offset": offset,
        "search_mode": search_mode,
    }

    if base_material_name_like:
        params["base_material_name_like"] = base_material_name_like
    if inventory_number:
        params["inventory_number"] = inventory_number
    if serial_number:
        params["serial_number"] = serial_number
    if employee_id:
        params["employee_id"] = employee_id

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(SAP_API_URL, params=params)
        response.raise_for_status()
        return response.json()


async def _get_local_assets_by_material_ids(
        db: AsyncSession,
        material_ids: List[int],
) -> list[Any] | Sequence[Any]:
    """Массовая загрузка локальных активов по material_id."""
    if not material_ids:
        return []

    query = (
        select(Asset)
        .options(
            selectinload(Asset.asset_type),
            selectinload(Asset.asset_status),
            selectinload(Asset.model),
            selectinload(Asset.parent).options(
                selectinload(Asset.asset_type),
                selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
            ),
            selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
            selectinload(Asset.assignments).options(
                selectinload(AssetAssignment.employee)
            ),
        )
        .where(Asset.material_id.in_(material_ids))
    )

    result = await db.execute(query)
    return result.scalars().all()


async def _get_employees_by_ids(
        db: AsyncSession,
        employee_ids: List[str],
) -> list[Any] | Sequence[Any]:
    """Массовая загрузка сотрудников по employee_id."""
    if not employee_ids:
        return []

    query = select(Employee).where(Employee.employee_id.in_(employee_ids))
    result = await db.execute(query)
    return result.scalars().all()


async def _get_departments_by_codes(
        db: AsyncSession,
        department_codes: List[str],
) -> list[Any] | Sequence[Any]:
    """Массовая загрузка подразделений по short_name (department_code)."""
    if not department_codes:
        return []

    query = select(ZupDepartment).where(ZupDepartment.short_name.in_(department_codes))
    result = await db.execute(query)
    return result.scalars().all()


def _build_virtual_asset(
        sap_item: Dict[str, Any],
        employees_map: Dict[str, Employee],
        departments_map: Dict[str, ZupDepartment],
) -> Dict[str, Any]:
    employee_id = sap_item.get("employee_id")
    employee = employees_map.get(employee_id) if employee_id else None

    users = []
    if employee:
        users.append(_build_user_response(employee, "user"))

    current_user_full_name = None
    if employee:
        parts = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
        current_user_full_name = " ".join(parts) if parts else None

    # ГАРАНТИЯ: asset_id всегда должен быть int для Pydantic.
    # Если SAP API еще не отдает material_id (возвращает null), генерируем стабильный хеш.
    raw_material_id = sap_item.get("material_id")
    if raw_material_id is not None:
        asset_id_val = int(raw_material_id)
    else:
        inv = str(sap_item.get("inventory_number", ""))
        serial = str(sap_item.get("serial_number", ""))
        # Создаем стабильное 32-битное целое число из строки (всегда будет int)
        # asset_id_val = int(hashlib.md5(f"{inv}_{serial}".encode()).hexdigest()[:8], 16)

        # zlib.crc32 возвращает беззнаковое 32-битное число.
        # Битовое И (&) с 0x7FFFFFFF (2147483647) гарантирует, что число
        # всегда поместится в знаковый INTEGER PostgreSQL и не вызовет переполнения.
        asset_id_val = zlib.crc32(f"{inv}_{serial}".encode()) & 0x7FFFFFFF

    return {
        "asset_id": asset_id_val,  # <-- Теперь здесь гарантированно int
        "name": sap_item.get("base_material_name"),
        "inventory_id": sap_item.get("inventory_number"),
        "serial_number": sap_item.get("serial_number"),
        "quantity": int(sap_item.get("quantity", 0)),  # <-- Гарантируем int
        "asset_status": None,
        "asset_status_id": None,
        "comment": None,
        "date_issue": None,
        "date_purchasing": None,
        "model_id": None,
        "model_name": None,
        "asset_type_id": None,
        "parent_id": None,
        "every_week_check": False,
        "next_service": None,
        "service_period": 0,
        "parent_name": None,
        "manufacturer_name": None,
        "vendor_name": None,
        "os_name": None,
        "created_by": None,
        "updated_by": None,
        "created_at": None,  # <-- Теперь схема разрешает None
        "updated_at": None,  # <-- Теперь схема разрешает None
        "asset_type_name": None,
        "location": None,
        "users": users,
        "responsible_users": [],
        "serving_users": [],
        "current_user": employee_id,
        "current_user_full_name": current_user_full_name,
        "parent": None,
    }


def _build_user_response(employee: Employee, assignment_type: str) -> Dict[str, Any]:
    """Формирование ответа пользователя для виртуального актива."""
    parts_ru = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
    parts_en = [p for p in [employee.last_name_en, employee.first_name_en, employee.middle_name_en] if p]

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
        "created_at": employee.created_at,
        "updated_at": employee.updated_at,
        "full_name_ru": " ".join(parts_ru) if parts_ru else None,
        "full_name_en": " ".join(parts_en) if parts_en else None,
        "society": None,
        "department": None,
        "division": None,
        "group": None,
        "position": None,
        "start_date": None,
        "end_date": None,
        "assignment_type": assignment_type,
    }