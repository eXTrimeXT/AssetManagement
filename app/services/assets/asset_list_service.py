import logging
import zlib
from typing import List, Dict, Optional, Any, Sequence, Tuple

from fastapi.params import Depends
from sqlalchemy import select, func, inspect, Integer, or_, cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import httpx

from app.models.assets.Asset import Asset
from app.models.assets.AssetAssignment import AssetAssignment
from app.models.assets.AssetStatus import AssetStatus
from app.models.map_assets.AssetPosition import AssetPosition
from app.models.zup.employee import Employee
from app.models.zup.department import ZupDepartment
from app.schemas.assets.AssetSchemas import AssetResponse

logger = logging.getLogger(__name__)

SAP_API_URL = "http://10.168.143.7:8123/sap/base_materials"


async def get_assets_list_with_sap(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 50,
        asset_id: Optional[int] = None,
        material_id: Optional[str] = None,
        name: Optional[str] = None,
        inventory_id: Optional[str] = None,
        serial_number: Optional[str] = None,
        asset_status: Optional[str] = None,
        model_id: Optional[int] = None,
        asset_type_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        employee_id: Optional[str] = None,
        only_my: Optional[bool] = False,
        search_mode: str = "not_nulls",
) -> Dict[str, Any]:
    """
    Получение списка активов: Локальные данные имеют абсолютный приоритет.
    Список дополняется данными из SAP API, если локальных записей недостаточно.
    """
    # === ОПТИМИЗАЦИЯ 1: Прямой поиск по уникальным идентификаторам ===
    if material_id is not None or asset_id is not None:
        local_orm_items = await _get_local_assets_slice(
            db=db, skip=0, limit=1,
            asset_id=asset_id, material_id=material_id,
            name=name, inventory_id=inventory_id, serial_number=serial_number,
            asset_status=asset_status, model_id=model_id, asset_type_id=asset_type_id,
            parent_id=parent_id, employee_id=employee_id, only_my=only_my
        )

        if local_orm_items:
            local_items = [AssetResponse.model_validate(item, from_attributes=True) for item in local_orm_items]
            return _build_paginated_response(local_items, total=1, page=1, page_size=1)
        # return _build_paginated_response([], total=0, page=1, page_size=1)

    # === ОПТИМИЗАЦИЯ 2: Если запрошен asset_type_id != 10, SAP не запрашиваем ===
    # Все виртуальные активы из SAP имеют asset_type_id = 10.
    # Если фильтр требует другой тип, ни один виртуальный актив не пройдет фильтрацию.
    skip_sap_fetch = (asset_type_id is not None and asset_type_id != 10)
    logger.debug(f"skip_sap_fetch = {skip_sap_fetch}")

    # === Получаем локальные данные ===
    local_total = await _get_local_assets_count(
        db=db, asset_id=asset_id, material_id=material_id,
        name=name, inventory_id=inventory_id, serial_number=serial_number,
        asset_status=asset_status, model_id=model_id, asset_type_id=asset_type_id,
        parent_id=parent_id, employee_id=employee_id, only_my=only_my
    )

    skip = (page - 1) * page_size
    result_items: List[Any] = []
    sap_total = 0

    # Если на этой странице есть локальные активы, забираем их
    if skip < local_total:
        local_orm_items = await _get_local_assets_slice(
            db=db, skip=skip, limit=page_size,
            asset_id=asset_id, material_id=material_id,
            name=name, inventory_id=inventory_id, serial_number=serial_number,
            asset_status=asset_status, model_id=model_id, asset_type_id=asset_type_id,
            parent_id=parent_id, employee_id=employee_id, only_my=only_my
        )

        local_items = [AssetResponse.model_validate(item, from_attributes=True) for item in local_orm_items]
        result_items.extend(local_items)

        # Дополняем из SAP, только если есть место и SAP не пропускаем
        remaining_slots = page_size - len(result_items)
        if remaining_slots > 0 and not skip_sap_fetch:
            exclude_inv_ids = [item.inventory_id for item in result_items]
            sap_items, fetched_sap_total = await _fetch_and_merge_sap_assets(
                db=db, limit=remaining_slots * 2, offset=0,
                material_id=material_id, name=name,
                inventory_id=inventory_id, serial_number=serial_number,
                employee_id=employee_id, search_mode=search_mode,
                exclude_inventory_ids=exclude_inv_ids, asset_type_id=asset_type_id, only_my=only_my
            )
            result_items.extend(sap_items[:remaining_slots])
            sap_total = fetched_sap_total
    else:
        # Локальные активы закончились, запрашиваем только SAP (если не пропускаем)
        if not skip_sap_fetch:
            sap_offset = skip - local_total
            sap_items, fetched_sap_total = await _fetch_and_merge_sap_assets(
                db=db, limit=page_size, offset=sap_offset,
                material_id=material_id, name=name,
                inventory_id=inventory_id, serial_number=serial_number,
                employee_id=employee_id, search_mode=search_mode,
                exclude_inventory_ids=[], asset_type_id=asset_type_id, only_my=only_my
            )
            result_items.extend(sap_items)
            sap_total = fetched_sap_total

    # Итоговый total
    final_total = local_total + sap_total

    return _build_paginated_response(result_items, final_total, page, page_size)


async def _get_local_assets_count(
        db: AsyncSession,
        asset_id: Optional[int],
        material_id: Optional[str],
        name: Optional[str],
        inventory_id: Optional[str],
        serial_number: Optional[str],
        asset_status: Optional[str],
        model_id: Optional[int],
        asset_type_id: Optional[int],
        parent_id: Optional[int],
        employee_id: Optional[str],
        only_my: Optional[bool] = False
) -> int:
    """Подсчет количества локальных активов по всем фильтрам."""
    query = select(func.count(Asset.asset_id))

    if asset_id:
        query = query.where(Asset.asset_id == asset_id)
    if material_id:
        query = query.where(Asset.material_id == material_id)
    if name:
        query = query.where(Asset.name.ilike(f"%{name}%"))
    if inventory_id:
        query = query.where(Asset.inventory_id.ilike(f"%{inventory_id}%"))
    if serial_number:
        query = query.where(Asset.serial_number.ilike(f"%{serial_number}%"))
    if model_id is not None:
        query = query.where(Asset.model_id == model_id)
    if asset_type_id is not None:
        query = query.where(Asset.asset_type_id == asset_type_id)
    if parent_id is not None:
        query = query.where(Asset.parent_id == parent_id)
    if asset_status:
        query = query.join(AssetStatus, Asset.asset_status_id == AssetStatus.id)
        query = query.where(AssetStatus.status == asset_status)
    if employee_id:
        emp_asset_subq = (
            select(AssetAssignment.asset_id)
            .where(AssetAssignment.employee_id == employee_id)
            .scalar_subquery()
        )
        if only_my:
            # Ключевое условие: исключаем архивные привязки
            emp_asset_subq = emp_asset_subq.where(AssetAssignment.end_date.is_(None))

        query = query.where(Asset.asset_id.in_(emp_asset_subq))

    result = await db.execute(query)
    return result.scalar_one() or 0


async def _get_local_assets_slice(
        db: AsyncSession,
        skip: int,
        limit: int,
        asset_id: Optional[int],
        material_id: Optional[str],
        name: Optional[str],
        inventory_id: Optional[str],
        serial_number: Optional[str],
        asset_status: Optional[str],
        model_id: Optional[int],
        asset_type_id: Optional[int],
        parent_id: Optional[int],
        employee_id: Optional[str],
        only_my: Optional[bool] = False
) -> Sequence[Asset]:
    """Получение среза локальных активов с полной загрузкой связей."""
    query = select(Asset).options(
        selectinload(Asset.asset_type),
        selectinload(Asset.asset_status),
        selectinload(Asset.model),
        selectinload(Asset.parent).options(
            selectinload(Asset.asset_type),
            selectinload(Asset.asset_status),
            selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
        ),
        selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
        selectinload(Asset.assignments).options(
            selectinload(AssetAssignment.employee).options(
                selectinload(Employee.position),
                selectinload(Employee.group).options(
                    selectinload(ZupDepartment.parent).options(
                        selectinload(ZupDepartment.parent).options(
                            selectinload(ZupDepartment.parent)
                        )
                    )
                )
            )
        ),
    )

    if asset_id:
        query = query.where(Asset.asset_id == asset_id)
    if material_id:
        query = query.where(Asset.material_id == material_id)
    if name:
        query = query.where(Asset.name.ilike(f"%{name}%"))
    if inventory_id:
        query = query.where(Asset.inventory_id.ilike(f"%{inventory_id}%"))
    if serial_number:
        query = query.where(Asset.serial_number.ilike(f"%{serial_number}%"))
    if model_id is not None:
        query = query.where(Asset.model_id == model_id)
    if asset_type_id is not None:
        query = query.where(Asset.asset_type_id == asset_type_id)
    if parent_id is not None:
        query = query.where(Asset.parent_id == parent_id)
    if asset_status:
        query = query.join(AssetStatus, Asset.asset_status_id == AssetStatus.id)
        query = query.where(AssetStatus.status == asset_status)
    if employee_id:
        emp_asset_subq = (
            select(AssetAssignment.asset_id)
            .where(AssetAssignment.employee_id == employee_id)
            .scalar_subquery()
        )
        if only_my:
            emp_asset_subq = emp_asset_subq.where(AssetAssignment.end_date.is_(None))

        query = query.where(Asset.asset_id.in_(emp_asset_subq.scalar_subquery()))

    query = query.order_by(Asset.asset_id.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


# async def _fetch_and_merge_sap_assets(
#         db: AsyncSession,
#         limit: int,
#         offset: int,
#         material_id: Optional[str],
#         name: Optional[str],
#         inventory_id: Optional[str],
#         serial_number: Optional[str],
#         employee_id: Optional[str],
#         search_mode: str,
#         exclude_inventory_ids: List[str],
#         asset_type_id: Optional[int],
#         only_my: Optional[bool] = False
# ) -> Tuple[List[Dict[str, Any]], int]:
#     """Запрос к SAP и слияние с исключением дубликатов."""
#     try:
#         sap_response = await fetch_sap_materials(
#             page=1,
#             page_size=limit,
#             material_id=material_id,
#             search_mode=search_mode,
#             base_material_name_like=name,
#             inventory_number=inventory_id,
#             serial_number=serial_number,
#             employee_id=employee_id,
#         )
#
#         if not sap_response.get("success") or "data" not in sap_response.get("response", {}):
#             return [], 0
#
#         sap_data = sap_response["response"]
#         sap_items_raw = sap_data.get("data", [])
#         sap_total = sap_data.get("total", 0)
#
#         # Фильтрация дубликатов
#         filtered_sap_items = []
#         employee_ids = set()
#         department_codes = set()
#
#         for item in sap_items_raw:
#             if item.get("inventory_number") in exclude_inventory_ids:
#                 continue
#             filtered_sap_items.append(item)
#
#             if item.get("employee_id"):
#                 employee_ids.add("00" + item["employee_id"])
#             if item.get("department_code"):
#                 department_codes.add(item["department_code"])
#
#         # Массовая загрузка сотрудников и департаментов
#         employees_map = {}
#         if only_my and employee_ids:
#             employees = await _get_employees_by_ids(db, list(employee_ids))
#             employees_map = {emp.employee_id: emp for emp in employees}
#
#         departments_map = {}
#         if department_codes:
#             departments = await _get_departments_by_codes(db, list(department_codes))
#             departments_map = {dept.short_name: dept for dept in departments}
#
#         # Сборка виртуальных активов
#         virtual_assets = []
#         for sap_item in filtered_sap_items:
#             virtual_asset = _build_virtual_asset(sap_item, employees_map, departments_map)
#             # Все виртуальные активы имеют asset_type_id = 10
#             # Если запрошен другой тип, они не пройдут фильтрацию
#             if asset_type_id is None or asset_type_id == 10:
#                 virtual_assets.append(virtual_asset)
#
#         return virtual_assets, sap_total
#
#     except Exception as e:
#         logger.error(f"[SAP FALLBACK] Ошибка при запросе к SAP API: {e}", exc_info=True)
#         return [], 0

# async def _fetch_and_merge_sap_assets(
#         db: AsyncSession,
#         limit: int,
#         offset: int,
#         material_id: Optional[str],
#         name: Optional[str],
#         inventory_id: Optional[str],
#         serial_number: Optional[str],
#         employee_id: Optional[str],
#         search_mode: str,
#         exclude_inventory_ids: List[str],
#         asset_type_id: Optional[int],
#         only_my: Optional[bool] = False,
# ) -> Tuple[List[Dict[str, Any]], int]:
#     """Запрос к SAP и слияние с исключением дубликатов и 'призрачных' SAP активов."""
#     try:
#         sap_response = await fetch_sap_materials(
#             page=1,
#             page_size=limit,
#             material_id=material_id,
#             search_mode=search_mode,
#             base_material_name_like=name,
#             inventory_number=inventory_id,
#             serial_number=serial_number,
#             employee_id=employee_id,
#         )
#
#         if not sap_response.get("success") or "data" not in sap_response.get("response", {}):
#             return [], 0
#
#         sap_data = sap_response["response"]
#         sap_items_raw = sap_data.get("data", [])
#         sap_total = sap_data.get("total", 0)
#
#         # === НОВОЕ: Получаем все inventory_id и material_id, которые УЖЕ есть в локальной БД среди текущих SAP-кандидатов ===
#         sap_inventory_ids = [item.get("inventory_number") for item in sap_items_raw if item.get("inventory_number")]
#         sap_material_ids = [item.get("material_id") for item in sap_items_raw if item.get("material_id")]
#
#         local_inv_ids_to_exclude = set()
#         local_mat_ids_to_exclude = set()
#
#         if sap_inventory_ids or sap_material_ids:
#             conditions = []
#             if sap_inventory_ids:
#                 conditions.append(Asset.inventory_id.in_(sap_inventory_ids))
#             if sap_material_ids:
#                 conditions.append(Asset.material_id.in_(sap_material_ids))
#
#             # Ищем любые локальные активы с такими идентификаторами
#             existing_query = select(Asset.inventory_id, Asset.material_id).where(or_(*conditions))
#             existing_result = await db.execute(existing_query)
#             existing_records = existing_result.all()
#
#             local_inv_ids_to_exclude = {rec.inventory_id for rec in existing_records if rec.inventory_id}
#             local_mat_ids_to_exclude = {rec.material_id for rec in existing_records if rec.material_id}
#
#         filtered_sap_items = []
#         employee_ids = set()
#         department_codes = set()
#
#         for item in sap_items_raw:
#             inv_num = item.get("inventory_number")
#             mat_id = item.get("material_id")
#
#             # Исключаем, если уже есть на текущей странице локальных результатов (старая логика)
#             if inv_num in exclude_inventory_ids:
#                 continue
#
#             # НОВАЯ ЛОГИКА: Исключаем, если этот актив УЖЕ существует в локальной БД в принципе.
#             # Это предотвращает появление "призрачного" SAP-актива, если локальный актив был передан другому лицу.
#             if inv_num in local_inv_ids_to_exclude or (mat_id and mat_id in local_mat_ids_to_exclude):
#                 continue
#
#             # Проверка only_my
#             if only_my and employee_id:
#                 sap_emp_id = "00" + str(item.get("employee_id", ""))
#                 # Сравниваем нормализованный ID из SAP с ID текущего пользователя
#                 if sap_emp_id != employee_id:
#                     continue
#
#             filtered_sap_items.append(item)
#
#             if item.get("employee_id"):
#                 employee_ids.add("00" + str(item["employee_id"]))
#             if item.get("department_code"):
#                 department_codes.add(item["department_code"])
#
#         # Массовая загрузка сотрудников и департаментов
#         employees_map = {}
#         if employee_ids:
#             employees = await _get_employees_by_ids(db, list(employee_ids))
#             employees_map = {emp.employee_id: emp for emp in employees}
#
#         departments_map = {}
#         if department_codes:
#             departments = await _get_departments_by_codes(db, list(department_codes))
#             departments_map = {dept.short_name: dept for dept in departments}
#
#         # Сборка виртуальных активов
#         virtual_assets = []
#         for sap_item in filtered_sap_items:
#             virtual_asset = _build_virtual_asset(sap_item, employees_map, departments_map)
#             if asset_type_id is None or asset_type_id == 10:
#                 virtual_assets.append(virtual_asset)
#
#         return virtual_assets, sap_total
#
#     except Exception as e:
#         logger.error(f"[SAP FALLBACK] Ошибка при запросе к SAP API: {e}", exc_info=True)
#         return [], 0

# async def _fetch_and_merge_sap_assets(
#         db: AsyncSession,
#         limit: int,
#         offset: int,
#         material_id: Optional[str],
#         name: Optional[str],
#         inventory_id: Optional[str],
#         serial_number: Optional[str],
#         employee_id: Optional[str],
#         search_mode: str,
#         exclude_inventory_ids: List[str],
#         asset_type_id: Optional[int],
#         only_my: bool = False,
# ) -> Tuple[List[Dict[str, Any]], int]:
#     """Запрос к SAP и слияние с исключением дубликатов и 'призрачных' SAP активов."""
#     try:
#         sap_response = await fetch_sap_materials(
#             page=1,
#             page_size=limit,
#             material_id=material_id,
#             search_mode=search_mode,
#             base_material_name_like=name,
#             inventory_number=inventory_id,
#             serial_number=serial_number,
#             employee_id=employee_id,
#         )
#
#         if not sap_response.get("success") or "data" not in sap_response.get("response", {}):
#             return [], 0
#
#         sap_data = sap_response["response"]
#         sap_items_raw = sap_data.get("data", [])
#         sap_total = sap_data.get("total", 0)
#
#         # === Получаем все inventory_id и material_id, которые УЖЕ есть в локальной БД ===
#         sap_inventory_ids = [item.get("inventory_number") for item in sap_items_raw if item.get("inventory_number")]
#         sap_material_ids = [item.get("material_id") for item in sap_items_raw if item.get("material_id")]
#
#         local_inv_ids_to_exclude = set()
#         local_mat_ids_to_exclude = set()
#
#         if sap_inventory_ids or sap_material_ids:
#             conditions = []
#             if sap_inventory_ids:
#                 conditions.append(Asset.inventory_id.in_(sap_inventory_ids))
#             if sap_material_ids:
#                 conditions.append(Asset.material_id.in_(sap_material_ids))
#
#             existing_query = select(Asset.inventory_id, Asset.material_id).where(or_(*conditions))
#             existing_result = await db.execute(existing_query)
#             existing_records = existing_result.all()
#
#             local_inv_ids_to_exclude = {rec.inventory_id for rec in existing_records if rec.inventory_id}
#             local_mat_ids_to_exclude = {rec.material_id for rec in existing_records if rec.material_id}
#
#         filtered_sap_items = []
#         employee_ids = set()
#         department_codes = set()
#
#         # === НОВОЕ: Счетчик исключенных элементов для коррекции total ===
#         excluded_count = 0
#
#         for item in sap_items_raw:
#             inv_num = item.get("inventory_number")
#             mat_id = item.get("material_id")
#
#             is_excluded = False
#
#             # 1. Исключаем, если уже есть на текущей странице локальных результатов
#             if inv_num in exclude_inventory_ids:
#                 is_excluded = True
#
#             # 2. Исключаем, если этот актив УЖЕ существует в локальной БД в принципе
#             elif inv_num in local_inv_ids_to_exclude or (mat_id and mat_id in local_mat_ids_to_exclude):
#                 is_excluded = True
#
#             # 3. Проверка only_my
#             elif only_my and employee_id:
#                 sap_emp_id = "00" + str(item.get("employee_id", ""))
#                 if sap_emp_id != employee_id:
#                     is_excluded = True
#
#             if is_excluded:
#                 excluded_count += 1
#                 continue
#
#             filtered_sap_items.append(item)
#
#             if item.get("employee_id"):
#                 employee_ids.add("00" + str(item["employee_id"]))
#             if item.get("department_code"):
#                 department_codes.add(item["department_code"])
#
#         # Массовая загрузка сотрудников и департаментов
#         employees_map = {}
#         if employee_ids:
#             employees = await _get_employees_by_ids(db, list(employee_ids))
#             employees_map = {emp.employee_id: emp for emp in employees}
#
#         departments_map = {}
#         if department_codes:
#             departments = await _get_departments_by_codes(db, list(department_codes))
#             departments_map = {dept.short_name: dept for dept in departments}
#
#         # Сборка виртуальных активов
#         virtual_assets = []
#         for sap_item in filtered_sap_items:
#             virtual_asset = _build_virtual_asset(sap_item, employees_map, departments_map)
#             if asset_type_id is None or asset_type_id == 10:
#                 virtual_assets.append(virtual_asset)
#
#         # === НОВОЕ: Корректируем общее количество SAP-активов, вычитая исключенные ===
#         adjusted_sap_total = max(0, sap_total - excluded_count)
#
#         return virtual_assets, adjusted_sap_total
#
#     except Exception as e:
#         logger.error(f"[SAP FALLBACK] Ошибка при запросе к SAP API: {e}", exc_info=True)
#         return [], 0

async def _fetch_and_merge_sap_assets(
        db: AsyncSession,
        limit: int,
        offset: int,
        material_id: Optional[str],
        name: Optional[str],
        inventory_id: Optional[str],
        serial_number: Optional[str],
        employee_id: Optional[str],
        search_mode: str,
        exclude_inventory_ids: List[str],
        asset_type_id: Optional[int],
        only_my: bool = False,
) -> Tuple[List[Dict[str, Any]], int]:
    """Запрос к SAP и слияние с исключением дубликатов и 'призрачных' SAP активов."""
    try:
        sap_response = await fetch_sap_materials(
            page=1,
            page_size=limit,
            material_id=material_id,
            search_mode=search_mode,
            base_material_name_like=name,
            inventory_number=inventory_id,
            serial_number=serial_number,
            employee_id=employee_id,
        )

        if not sap_response.get("success") or "data" not in sap_response.get("response", {}):
            return [], 0

        sap_data = sap_response["response"]
        sap_items_raw = sap_data.get("data", [])
        sap_total = sap_data.get("total", 0)

        logger.debug(f"[SAP DEBUG] SAP вернул total={sap_total}, элементов в data={len(sap_items_raw)}")

        # Собираем все инвентарные и материальные ID из текущей выдачи SAP с нормализацией
        sap_inventory_ids = [str(item.get("inventory_number")).strip().lower() for item in sap_items_raw if item.get("inventory_number")]
        sap_material_ids = [str(item.get("material_id")).strip().lower() for item in sap_items_raw if item.get("material_id")]

        local_inv_ids_to_exclude = set()
        local_mat_ids_to_exclude = set()

        if sap_inventory_ids or sap_material_ids:
            conditions = []
            if sap_inventory_ids:
                conditions.append(Asset.inventory_id.in_(sap_inventory_ids))
            if sap_material_ids:
                conditions.append(Asset.material_id.in_(sap_material_ids))

            existing_query = select(Asset.inventory_id, Asset.material_id).where(or_(*conditions))
            existing_result = await db.execute(existing_query)
            existing_records = existing_result.all()

            local_inv_ids_to_exclude = {str(rec.inventory_id).strip().lower() for rec in existing_records if rec.inventory_id}
            local_mat_ids_to_exclude = {str(rec.material_id).strip().lower() for rec in existing_records if rec.material_id}

        filtered_sap_items = []
        employee_ids = set()
        department_codes = set()
        excluded_count = 0

        target_emp_id = str(employee_id).strip() if employee_id else ""
        normalize_emp_id = lambda x: "00" + str(x).strip() if x else ""

        for item in sap_items_raw:
            inv_num = str(item.get("inventory_number", "")).strip().lower()
            mat_id = str(item.get("material_id", "")).strip().lower()

            is_excluded = False

            # 1. Исключаем, если уже есть на текущей странице локальных результатов
            norm_exclude_ids = [str(x).strip().lower() for x in exclude_inventory_ids]
            if inv_num and inv_num in norm_exclude_ids:
                is_excluded = True

            # 2. Исключаем, если этот актив УЖЕ существует в локальной БД в принципе
            elif inv_num and inv_num in local_inv_ids_to_exclude:
                is_excluded = True
            elif mat_id and mat_id in local_mat_ids_to_exclude:
                is_excluded = True

            # 3. Проверка only_my
            elif only_my and target_emp_id:
                sap_emp_id = normalize_emp_id(item.get("employee_id"))
                if sap_emp_id != target_emp_id:
                    is_excluded = True

            if is_excluded:
                excluded_count += 1
                logger.debug(f"[SAP DEBUG] ИСКЛЮЧЕН актив: inv='{inv_num}', mat='{mat_id}'.")
                continue

            filtered_sap_items.append(item)

            if item.get("employee_id"):
                employee_ids.add(normalize_emp_id(item["employee_id"]))
            if item.get("department_code"):
                department_codes.add(item["department_code"])

        # Массовая загрузка сотрудников и департаментов
        employees_map = {}
        if employee_ids:
            employees = await _get_employees_by_ids(db, list(employee_ids))
            employees_map = {emp.employee_id: emp for emp in employees}

        departments_map = {}
        if department_codes:
            departments = await _get_departments_by_codes(db, list(department_codes))
            departments_map = {dept.short_name: dept for dept in departments}

        virtual_assets = []
        for sap_item in filtered_sap_items:
            virtual_asset = _build_virtual_asset(sap_item, employees_map, departments_map)
            if asset_type_id is None or asset_type_id == 10:
                virtual_assets.append(virtual_asset)

        # === НОВОЕ: Умная корректировка total ===
        real_sap_items_count = len(filtered_sap_items) + excluded_count

        # Если SAP вернул total больше, чем реальное количество элементов в его же ответе (при offset=0),
        # значит, SAP сам отфильтровал эти элементы, но забыл обновить total. Мы исправляем это.
        if offset == 0 and real_sap_items_count < sap_total:
            adjusted_sap_total = len(filtered_sap_items)
            logger.debug(f"[SAP DEBUG] SAP total ({sap_total}) не совпадает с реальным количеством ({real_sap_items_count}). Корректируем total до {adjusted_sap_total}.")
        else:
            adjusted_sap_total = max(0, sap_total - excluded_count)
            logger.debug(f"[SAP DEBUG] Стандартная корректировка: sap_total={sap_total}, исключено={excluded_count}, adjusted={adjusted_sap_total}")

        return virtual_assets, adjusted_sap_total

    except Exception as e:
        logger.error(f"[SAP FALLBACK] Ошибка при запросе к SAP API: {e}", exc_info=True)
        return [], 0

async def fetch_sap_materials(
        page: int,
        page_size: int,
        material_id: Optional[str],
        search_mode: str = "ALL",
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
        "employee_id_search_mode": search_mode,
    }

    if material_id:
        params["material_id"] = material_id
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


async def _get_employees_by_ids(
        db: AsyncSession,
        employee_ids: List[str],
) -> list[Any] | Sequence[Any]:
    """Массовая загрузка сотрудников по employee_id с учетом разного количества ведущих нулей."""
    if not employee_ids:
        return []

    numeric_ids = []
    string_ids = []
    for eid in employee_ids:
        try:
            numeric_ids.append(int(eid))
        except (ValueError, TypeError):
            string_ids.append(eid)

    conditions = []
    if numeric_ids:
        conditions.append(cast(Employee.employee_id, Integer).in_(numeric_ids))
    if string_ids:
        conditions.append(Employee.employee_id.in_(string_ids))

    query = (
        select(Employee)
        .options(
            selectinload(Employee.position),
            selectinload(Employee.group).options(
                selectinload(ZupDepartment.parent).options(
                    selectinload(ZupDepartment.parent).options(
                        selectinload(ZupDepartment.parent)
                    )
                )
            )
        )
        .where(or_(*conditions))
    )

    result = await db.execute(query)
    employees = result.scalars().all()

    for emp in employees:
        hierarchy_chain = []
        current = emp.group
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
        emp.society = hierarchy_chain[0] if len(hierarchy_chain) >= 1 else None
        emp.department = hierarchy_chain[1] if len(hierarchy_chain) >= 2 else None
        emp.division = hierarchy_chain[2] if len(hierarchy_chain) >= 3 else None
        emp.group = hierarchy_chain[3] if len(hierarchy_chain) >= 4 else None

    return employees


async def _get_departments_by_codes(
        db: AsyncSession,
        department_codes: List[str],
) -> list[Any] | Sequence[Any]:
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
    raw_employee_id = "00" + str(sap_item.get("employee_id")) if sap_item.get("employee_id") else None
    employee = employees_map.get(raw_employee_id) if raw_employee_id else None

    start_date = sap_item.get("changed_date") if sap_item.get("changed_date") else None

    users = []
    if employee:
        users.append(_build_user_response(employee, "user", start_date))

    current_user_full_name = None
    if employee:
        parts = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
        current_user_full_name = " ".join(parts) if parts else None

    raw_material_id = sap_item.get("material_id")
    # if raw_material_id is not None:
    #     try:
    #         asset_id_val = int(raw_material_id)
    #     except (ValueError, OverflowError):
    #         asset_id_val = zlib.crc32(str(raw_material_id).encode()) & 0x7FFFFFFF
    # else:
    #     inv = str(sap_item.get("inventory_number", ""))
    #     serial = str(sap_item.get("serial_number", ""))
    #     asset_id_val = zlib.crc32(f"{inv}_{serial}".encode()) & 0x7FFFFFFF

    return {
        "asset_id": None,
        "name": sap_item.get("base_material_name"),
        "inventory_id": sap_item.get("inventory_number"),
        "serial_number": sap_item.get("serial_number"),
        "quantity": int(sap_item.get("quantity", 0)) if sap_item.get("quantity") is not None else 0,
        "asset_status": "На складе",
        "asset_status_id": 9,
        "comment": None,
        "date_issue": None,
        "date_purchasing": None,
        "model_id": None,
        "model_name": None,
        "parent_id": None,
        "every_week_check": False,
        "next_service": None,
        "service_period": 0,
        "check_period": 0,
        "parent_name": None,
        "manufacturer_name": None,
        "vendor_name": None,
        "os_name": None,
        "created_by": None,
        "updated_by": None,
        "created_at": None,
        "updated_at": None,
        "asset_type_name": "Без типа",
        "asset_type_id": 11,
        "location": None,
        "users": users,

        # ответственный департамент
        "cost_center_code_from": sap_item.get("cost_center_code_from") if sap_item.get("cost_center_code_from") else None,
        "cost_center_name_from": sap_item.get("cost_center_name_from") if sap_item.get("cost_center_name_from") else None,
        "cost_center_shortname_from": sap_item.get("cost_center_shortname_from") if sap_item.get("cost_center_shortname_from") else None,

        # департамент владельца
        "cost_center_code": sap_item.get("cost_center_code") if sap_item.get("cost_center_code") else None,
        "cost_center_name": sap_item.get("cost_center_name") if sap_item.get("cost_center_name") else None,
        "cost_center_shortname": sap_item.get("cost_center_shortname") if sap_item.get("cost_center_shortname") else None,

        "serving_users": [],
        "current_user": raw_employee_id,
        "current_user_full_name": current_user_full_name,
        "parent": None,
        "material_id": raw_material_id
    }


def _build_user_response(employee: Employee, assignment_type: str, start_date: str) -> Dict[str, Any]:
    parts_ru = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
    parts_en = [p for p in [employee.last_name_en, employee.first_name_en, employee.middle_name_en] if p]

    format_start_date = start_date[:4] + "-" + start_date[4:6] + "-" + start_date[6:] if start_date and len(start_date) >= 8 else None

    position_data = None
    if getattr(employee, 'position', None):
        position_data = {
            "name": employee.position.name,
            "name_en": employee.position.name_en
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

    created_at = employee.__dict__.get('created_at')
    updated_at = employee.__dict__.get('updated_at')

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
        "created_at": created_at,
        "updated_at": updated_at,
        "full_name_ru": " ".join(parts_ru) if parts_ru else None,
        "full_name_en": " ".join(parts_en) if parts_en else None,
        "society": _get_dept_dict(getattr(employee, 'society', None)),
        "department": _get_dept_dict(getattr(employee, 'department', None)),
        "division": _get_dept_dict(getattr(employee, 'division', None)),
        "group": employee.__dict__.get('group'),
        "position": position_data,
        "start_date": format_start_date,
        "end_date": None,
        "assignment_type": assignment_type,
    }


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