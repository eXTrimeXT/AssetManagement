# import logging
# import zlib
# from typing import List, Dict, Optional, Any, Sequence
# from sqlalchemy import select, func, inspect, Integer, or_, cast
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.orm import selectinload
# import httpx
#
# from app.models.assets.Asset import Asset
# from app.models.assets.AssetAssignment import AssetAssignment
# from app.models.assets.AssetStatus import AssetStatus
# from app.models.map_assets.AssetPosition import AssetPosition
# from app.models.zup.employee import Employee
# from app.models.zup.department import ZupDepartment
#
# logger = logging.getLogger(__name__)
#
# SAP_API_URL = "http://10.168.143.7:8123/sap/base_materials"
#
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
#         employee_id: Optional[str] = None,
#         search_mode: str = "not_nulls",
# ) -> Dict[str, Any]:
#     """
#     Получение списка активов с слиянием данных из SAP API и локальной БД.
#     """
#
#     # Проверяем, есть ли фильтры, которые существуют ТОЛЬКО в локальной БД
#     has_local_only_filters = any([
#         asset_status is not None,
#         model_id is not None,
#         asset_type_id is not None,
#         parent_id is not None,
#         ])
#
#     # Если есть локальные фильтры, виртуальные активы из SAP всё равно не подойдут
#     # (у них эти поля равны None). Поэтому сразу идём в локальную БД.
#     # Это решает проблему пустых страниц при фильтрации по типу, модели и т.д.
#     # if asset_status is not None or model_id is not None or asset_type_id is not None or parent_id is not None:
#     if has_local_only_filters:
#         logger.info(f"[LOCAL FILTER] Обнаружен локальный фильтр (asset_type_id={asset_type_id}, model_id={model_id}), запрос идёт напрямую в БД.")
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
#     # Если локальных фильтров нет, работаем по стандартной схеме с SAP API
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
#     # Если SAP упал — возвращаем только локальные данные
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
#     # Если SAP вернул пустой список
#     if not sap_items:
#         return _build_paginated_response([], sap_total, page, page_size)
#
#     # Массовая загрузка локальных активов по material_id
#     material_ids = [item["material_id"] for item in sap_items if item.get("material_id")]
#     local_assets = await _get_local_assets_by_material_ids(db, material_ids)
#     local_assets_map = {asset.material_id: asset for asset in local_assets}
#
#     # Массовая загрузка сотрудников и департаментов
#     employee_ids = set()
#     department_codes = set()
#     for item in sap_items:
#         if item.get("employee_id"):
#             # Добавляем '00' для будущего поиска сотрудников из 1С (ZUP)
#             emp_id = "00" + item["employee_id"]
#             employee_ids.add(emp_id)
#             logger.debug(f"emp_id = {emp_id}")
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
#     # Слияние данных
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
#     return _build_paginated_response(result_items, sap_total, page, page_size)
#
# async def _get_local_assets_only(
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
#         employee_id: Optional[str] = None,
# ) -> Dict[str, Any]:
#     """
#     Резервный режим: SAP недоступен, возвращаем только локальные активы.
#     Все фильтры применяются на стороне БД.
#     """
#     logger.info("[SAP FALLBACK] Загрузка только локальных активов из БД")
#
#     # Строим базовый запрос
#     base_query = select(Asset).options(
#         selectinload(Asset.asset_type),
#         selectinload(Asset.asset_status),
#         selectinload(Asset.model),
#         selectinload(Asset.parent).options(
#             selectinload(Asset.asset_type),
#             selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
#         ),
#         selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
#         selectinload(Asset.assignments).options(
#             selectinload(AssetAssignment.employee).options(
#                 selectinload(Employee.position),
#                 selectinload(Employee.group).options(
#                     selectinload(ZupDepartment.parent).options(
#                         selectinload(ZupDepartment.parent).options(
#                             selectinload(ZupDepartment.parent)
#                         )
#                     )
#                 )
#             )
#         ),
#     )
#
#     # Применяем все фильтры
#     if name:
#         base_query = base_query.where(Asset.name.ilike(f"%{name}%"))
#     if inventory_id:
#         base_query = base_query.where(Asset.inventory_id.ilike(f"%{inventory_id}%"))
#     if serial_number:
#         base_query = base_query.where(Asset.serial_number.ilike(f"%{serial_number}%"))
#     if model_id is not None:
#         base_query = base_query.where(Asset.model_id == model_id)
#     if asset_type_id is not None:
#         base_query = base_query.where(Asset.asset_type_id == asset_type_id)
#     if parent_id is not None:
#         base_query = base_query.where(Asset.parent_id == parent_id)
#     if asset_status:
#         base_query = base_query.join(AssetStatus, Asset.asset_status_id == AssetStatus.id)
#         base_query = base_query.where(AssetStatus.status == asset_status)
#     if employee_id:
#         emp_asset_subq = (
#             select(AssetAssignment.asset_id)
#             .where(AssetAssignment.employee_id == employee_id)
#             .scalar_subquery()
#         )
#         base_query = base_query.where(Asset.asset_id.in_(emp_asset_subq))
#
#     # Считаем total
#     count_query = select(func.count()).select_from(base_query.subquery())
#     total_result = await db.execute(count_query)
#     total = total_result.scalar_one()
#
#     # Пагинация
#     skip = (page - 1) * page_size
#     items_query = base_query.order_by(Asset.asset_id).offset(skip).limit(page_size)
#     result = await db.execute(items_query)
#     items = result.scalars().all()
#
#     return _build_paginated_response(list(items), total, page, page_size)
#
#
# def _apply_local_filters(
#         items: List[Any],
#         asset_status: Optional[str],
#         model_id: Optional[int],
#         asset_type_id: Optional[int],
#         parent_id: Optional[int],
# ) -> List[Any]:
#     """Применяет фильтры, которые существуют только в локальной БД."""
#     filtered = []
#     for item in items:
#         if isinstance(item, dict):
#             item_status = item.get("asset_status")
#             item_model_id = item.get("model_id")
#             item_asset_type_id = item.get("asset_type_id")
#             item_parent_id = item.get("parent_id")
#         else:
#             item_status = item.asset_status.status if item.asset_status else None
#             item_model_id = item.model_id
#             item_asset_type_id = item.asset_type_id
#             item_parent_id = item.parent_id
#
#         if asset_status is not None and item_status != asset_status:
#             continue
#         if model_id is not None and item_model_id != model_id:
#             continue
#         if asset_type_id is not None and item_asset_type_id != asset_type_id:
#             continue
#         if parent_id is not None and item_parent_id != parent_id:
#             continue
#
#         filtered.append(item)
#
#     return filtered
#
#
# def _build_paginated_response(
#         items: List[Any], total: int, page: int, page_size: int
# ) -> Dict[str, Any]:
#     total_pages = (total + page_size - 1) // page_size if total > 0 else 0
#     return {
#         "items": items,
#         "total": total,
#         "page": page,
#         "page_size": page_size,
#         "total_pages": total_pages,
#         "has_next": page < total_pages,
#         "has_previous": page > 1,
#     }
#
#
# async def _fetch_sap_materials(
#         page: int,
#         page_size: int,
#         search_mode: str = "not_nulls",
#         base_material_name_like: Optional[str] = None,
#         inventory_number: Optional[str] = None,
#         serial_number: Optional[str] = None,
#         employee_id: Optional[str] = None,
# ) -> Dict[str, Any]:
#     """Запрос к SAP API для получения списка материалов."""
#     offset = (page - 1) * page_size
#
#     params = {
#         "limit": page_size,
#         "offset": offset,
#         "search_mode": search_mode,
#     }
#
#     if base_material_name_like:
#         params["base_material_name_like"] = base_material_name_like
#     if inventory_number:
#         params["inventory_number"] = inventory_number
#     if serial_number:
#         params["serial_number"] = serial_number
#     if employee_id:
#         params["employee_id"] = employee_id
#
#     async with httpx.AsyncClient(timeout=30.0) as client:
#         response = await client.get(SAP_API_URL, params=params)
#         response.raise_for_status()
#         return response.json()
#
#
# async def _get_local_assets_by_material_ids(
#         db: AsyncSession,
#         material_ids: List[int],
# ) -> list[Any] | Sequence[Any]:
#     """Массовая загрузка локальных активов по material_id."""
#     if not material_ids:
#         return []
#
#     query = (
#         select(Asset)
#         .options(
#             selectinload(Asset.asset_type),
#             selectinload(Asset.asset_status),
#             selectinload(Asset.model),
#             selectinload(Asset.parent).options(
#                 selectinload(Asset.asset_type),
#                 selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
#             ),
#             selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
#             selectinload(Asset.assignments).options(
#                 selectinload(AssetAssignment.employee).options(
#                     selectinload(Employee.position),
#                     selectinload(Employee.group).options(
#                         selectinload(ZupDepartment.parent).options(
#                             selectinload(ZupDepartment.parent).options(
#                                 selectinload(ZupDepartment.parent)
#                             )
#                         )
#                     )
#                 )
#             ),
#         )
#         .where(Asset.material_id.in_(material_ids))
#     )
#
#     result = await db.execute(query)
#     return result.scalars().all()
#
# async def _get_employees_by_ids(
#         db: AsyncSession,
#         employee_ids: List[str],
# ) -> list[Any] | Sequence[Any]:
#     """Массовая загрузка сотрудников по employee_id с учетом разного количества ведущих нулей."""
#     if not employee_ids:
#         return []
#
#     logger.info(f"[DEBUG EMP] Исходные employee_id из SAP API: {employee_ids}")
#
#     # Разделяем ID на числовые и строковые для надежного поиска
#     numeric_ids = []
#     string_ids = []
#
#     for eid in employee_ids:
#         try:
#             # Преобразуем в int: "00002347" -> 2347, "000002347" -> 2347
#             numeric_ids.append(int(eid))
#         except (ValueError, TypeError):
#             # Если ID содержит буквы или спецсимволы, оставляем как строку
#             string_ids.append(eid)
#
#     # Формируем условия для WHERE
#     conditions = []
#     if numeric_ids:
#         # Сравниваем числовое значение колонки БД с нашими числами
#         conditions.append(cast(Employee.employee_id, Integer).in_(numeric_ids))
#     if string_ids:
#         conditions.append(Employee.employee_id.in_(string_ids))
#
#     query = (
#         select(Employee)
#         .options(
#             selectinload(Employee.position),
#             selectinload(Employee.group).options(
#                 selectinload(ZupDepartment.parent).options(
#                     selectinload(ZupDepartment.parent).options(
#                         selectinload(ZupDepartment.parent)
#                     )
#                 )
#             )
#         )
#         .where(or_(*conditions)) # Используем OR для объединения условий
#     )
#
#     result = await db.execute(query)
#     employees = result.scalars().all()
#
#     logger.info(f"[DEBUG EMP] Найдено сотрудников в БД: {len(employees)}")
#     if employees:
#         found_ids = [emp.employee_id for emp in employees]
#         logger.info(f"[DEBUG EMP] Реально найденные employee_id в БД: {found_ids}")
#
#     # Восстанавливаем иерархию подразделений для найденных сотрудников
#     for emp in employees:
#         hierarchy_chain = []
#         current = emp.group
#
#         while current is not None:
#             hierarchy_chain.append(current)
#             if not current.parent_guid or current.parent_guid == "00000000-0000-0000-0000-000000000000":
#                 break
#
#             insp = inspect(current)
#             parent_attr = insp.attrs.get('parent')
#             if parent_attr is None or parent_attr.loaded_value is None:
#                 break
#
#             current = parent_attr.loaded_value
#
#         hierarchy_chain.reverse()
#
#         emp.society = hierarchy_chain[0] if len(hierarchy_chain) >= 1 else None
#         emp.department = hierarchy_chain[1] if len(hierarchy_chain) >= 2 else None
#         emp.division = hierarchy_chain[2] if len(hierarchy_chain) >= 3 else None
#         emp.group = hierarchy_chain[3] if len(hierarchy_chain) >= 4 else None
#
#     return employees
#
# async def _get_departments_by_codes(
#         db: AsyncSession,
#         department_codes: List[str],
# ) -> list[Any] | Sequence[Any]:
#     """Массовая загрузка подразделений по short_name (department_code)."""
#     if not department_codes:
#         return []
#
#     query = select(ZupDepartment).where(ZupDepartment.short_name.in_(department_codes))
#     result = await db.execute(query)
#     return result.scalars().all()
#
# def _build_virtual_asset(
#         sap_item: Dict[str, Any],
#         employees_map: Dict[str, Employee],
#         departments_map: Dict[str, ZupDepartment],
# ) -> Dict[str, Any]:
#     raw_employee_id = "00" + str(sap_item.get("employee_id"))
#     logger.debug(f"raw_employee_id = {raw_employee_id}")
#     employee = None
#
#     if raw_employee_id:
#         # 1. Сначала пробуем найти по точному совпадению строки
#         employee = employees_map.get(raw_employee_id)
#
#         # 2. Если не нашли, пробуем найти по числовому значению
#         # if not employee:
#         #     try:
#         #         num_key = int(raw_employee_id)
#         #         employee = employees_map.get(num_key)
#         #     except (ValueError, TypeError):
#         #         pass
#
#     if raw_employee_id and not employee:
#         logger.warning(f"[SAP VIRTUAL] Сотрудник '{raw_employee_id}' не найден в локальной БД для актива {sap_item.get('inventory_number')}")
#
#     users = []
#     if employee:
#         users.append(_build_user_response(employee, "user"))
#
#     current_user_full_name = None
#     if employee:
#         parts = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
#         current_user_full_name = " ".join(parts) if parts else None
#
#     # Теперь material_id - это строка из SAP.
#     raw_material_id = sap_item.get("material_id")
#
#     # Для ответа фронтенду (если schema требует int для asset_id)
#     if raw_material_id is not None:
#         try:
#             asset_id_val = int(raw_material_id)
#         except (ValueError, OverflowError):
#             asset_id_val = zlib.crc32(str(raw_material_id).encode()) & 0x7FFFFFFF
#     else:
#         inv = str(sap_item.get("inventory_number", ""))
#         serial = str(sap_item.get("serial_number", ""))
#         asset_id_val = zlib.crc32(f"{inv}_{serial}".encode()) & 0x7FFFFFFF
#
#     return {
#         "asset_id": None,
#         "name": sap_item.get("base_material_name"),
#         "inventory_id": sap_item.get("inventory_number"),
#         "serial_number": sap_item.get("serial_number"),
#         "quantity": int(sap_item.get("quantity", 0)) if sap_item.get("quantity") is not None else 0,
#         "asset_status": None,
#         "asset_status_id": None,
#         "comment": None,
#         "date_issue": None,
#         "date_purchasing": None,
#         "model_id": None,
#         "model_name": None,
#         "asset_type_id": None,
#         "parent_id": None,
#         "every_week_check": False,
#         "next_service": None,
#         "service_period": 0,
#         "parent_name": None,
#         "manufacturer_name": None,
#         "vendor_name": None,
#         "os_name": None,
#         "created_by": None,
#         "updated_by": None,
#         "created_at": None,
#         "updated_at": None,
#         "asset_type_name": None,
#         "location": None,
#         "users": users,
#         "responsible_users": [],
#         "serving_users": [],
#         "current_user": raw_employee_id,
#         "current_user_full_name": current_user_full_name,
#         "parent": None,
#         "material_id": raw_material_id
#     }
#
# # def _build_user_response(employee: Employee, assignment_type: str) -> Dict[str, Any]:
# #     """Формирование ответа пользователя для виртуального актива с полной иерархией."""
# #     parts_ru = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
# #     parts_en = [p for p in [employee.last_name_en, employee.first_name_en, employee.middle_name_en] if p]
# #
# #     # Формируем данные о должности, если она есть
# #     position_data = None
# #     if getattr(employee, 'position', None):
# #         position_data = {
# #             "name": employee.position.name,
# #             "name_en": employee.position.name_en
# #         }
# #
# #     # Вспомогательная функция для безопасного извлечения полей подразделения
# #     def _get_dept_dict(dept_obj):
# #         if not dept_obj:
# #             return None
# #         return {
# #             "guid": dept_obj.guid,
# #             "name": dept_obj.name,
# #             "name_en": getattr(dept_obj, 'name_en', None),
# #             "short_name": getattr(dept_obj, 'short_name', None),
# #             "creation_date": getattr(dept_obj, 'creation_date', None),
# #             "closure_date": getattr(dept_obj, 'closure_date', None),
# #             "parent_guid": getattr(dept_obj, 'parent_guid', None),
# #         }
# #
# #     return {
# #         "guid": employee.guid,
# #         "employee_id": employee.employee_id,
# #         "birth_date": employee.birth_date,
# #         "employment_date": employee.employment_date,
# #         "dismissal_date": employee.dismissal_date,
# #         "phone": employee.phone,
# #         "email": employee.email,
# #         "comment": employee.comment,
# #         "position_guid": employee.position_guid,
# #         "department_guid": employee.department_guid,
# #         "created_at": employee.created_at,
# #         # "updated_at": employee.updated_at,
# #         "updated_at": None,
# #         "full_name_ru": " ".join(parts_ru) if parts_ru else None,
# #         "full_name_en": " ".join(parts_en) if parts_en else None,
# #
# #         # Заполняем иерархию из атрибутов, которые мы добавили в _get_employees_by_ids
# #         "society": _get_dept_dict(getattr(employee, 'society', None)),
# #         "department": _get_dept_dict(getattr(employee, 'department', None)),
# #         "division": _get_dept_dict(getattr(employee, 'division', None)),
# #         "group": _get_dept_dict(getattr(employee, 'group', None)),
# #         "position": position_data,
# #
# #         "start_date": None,
# #         "end_date": None,
# #         "assignment_type": assignment_type,
# #     }
#
# def _build_user_response(employee: Employee, assignment_type: str) -> Dict[str, Any]:
#     """Формирование ответа пользователя для виртуального актива с полной иерархией."""
#     parts_ru = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
#     parts_en = [p for p in [employee.last_name_en, employee.first_name_en, employee.middle_name_en] if p]
#
#     # Формируем данные о должности, если она есть
#     position_data = None
#     if getattr(employee, 'position', None):
#         position_data = {
#             "name": employee.position.name,
#             "name_en": employee.position.name_en
#         }
#
#     # Вспомогательная функция для безопасного извлечения полей подразделения
#     def _get_dept_dict(dept_obj):
#         if not dept_obj:
#             return None
#         return {
#             "guid": dept_obj.guid,
#             "name": dept_obj.name,
#             "name_en": getattr(dept_obj, 'name_en', None),
#             "short_name": getattr(dept_obj, 'short_name', None),
#             "creation_date": getattr(dept_obj, 'creation_date', None),
#             "closure_date": getattr(dept_obj, 'closure_date', None),
#             "parent_guid": getattr(dept_obj, 'parent_guid', None),
#         }
#
#     # БЕЗОПАСНОЕ чтение атрибутов напрямую из __dict__, чтобы избежать MissingGreenlet
#     # Это читает уже загруженные данные из памяти, не обращаясь к БД
#     created_at = employee.__dict__.get('created_at')
#     updated_at = employee.__dict__.get('updated_at')
#
#     return {
#         "guid": employee.guid,
#         "employee_id": employee.employee_id,
#         "birth_date": employee.birth_date,
#         "employment_date": employee.employment_date,
#         "dismissal_date": employee.dismissal_date,
#         "phone": employee.phone,
#         "email": employee.email,
#         "comment": employee.comment,
#         "position_guid": employee.position_guid,
#         "department_guid": employee.department_guid,
#
#         # Используем значения из __dict__
#         "created_at": created_at,
#         "updated_at": updated_at,
#
#         "full_name_ru": " ".join(parts_ru) if parts_ru else None,
#         "full_name_en": " ".join(parts_en) if parts_en else None,
#
#         # Заполняем иерархию из атрибутов, которые мы добавили в _get_employees_by_ids
#         "society": _get_dept_dict(getattr(employee, 'society', None)),
#         "department": _get_dept_dict(getattr(employee, 'department', None)),
#         "division": _get_dept_dict(getattr(employee, 'division', None)),
#         "group": _get_dept_dict(getattr(employee, 'group', None)),
#         "position": position_data,
#
#         "start_date": None,
#         "end_date": None,
#         "assignment_type": assignment_type,
#     }


import logging
import zlib
from typing import List, Dict, Optional, Any, Sequence, Tuple
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

logger = logging.getLogger(__name__)

SAP_API_URL = "http://10.168.143.7:8123/sap/base_materials"


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
    Получение списка активов: Локальные данные имеют абсолютный приоритет.
    Список дополняется данными из SAP API, если локальных записей недостаточно.
    """
    skip = (page - 1) * page_size

    # 1. Получаем общее количество локальных активов, подходящих под фильтры
    local_total = await _get_local_assets_count(
        db, name, inventory_id, serial_number, asset_status, model_id, asset_type_id, parent_id, employee_id
    )

    result_items = []
    sap_total = 0

    if skip < local_total:
        # 2. На этой странице есть локальные активы. Забираем их.
        local_items = await _get_local_assets_slice(
            db, skip, page_size, name, inventory_id, serial_number,
            asset_status, model_id, asset_type_id, parent_id, employee_id
        )
        result_items.extend(local_items)

        remaining_slots = page_size - len(result_items)
        if remaining_slots > 0:
            # 3. Дополняем недостающее количество из SAP, исключая уже найденные локальные inventory_id
            exclude_inv_ids = [item.inventory_id for item in result_items]
            sap_items, fetched_sap_total = await _fetch_and_merge_sap_assets(
                db=db,
                limit=remaining_slots * 2,  # Берем с запасом для фильтрации дубликатов в Python
                offset=0,  # SAP всегда начинаем с начала, так как мы фильтруем дубликаты
                name=name,
                inventory_id=inventory_id,
                serial_number=serial_number,
                employee_id=employee_id,
                search_mode=search_mode,
                exclude_inventory_ids=exclude_inv_ids
            )
            result_items.extend(sap_items[:remaining_slots])  # Обрезаем до нужного размера
            sap_total = fetched_sap_total
    else:
        # 4. Локальные активы закончились. Запрашиваем только SAP со смещением
        sap_offset = skip - local_total
        sap_items, fetched_sap_total = await _fetch_and_merge_sap_assets(
            db=db,
            limit=page_size,
            offset=sap_offset,
            name=name,
            inventory_id=inventory_id,
            serial_number=serial_number,
            employee_id=employee_id,
            search_mode=search_mode,
            exclude_inventory_ids=[]
        )
        result_items.extend(sap_items)
        sap_total = fetched_sap_total

    # Итоговый total - это сумма (приблизительная, но достаточная для пагинации)
    final_total = local_total + sap_total

    return _build_paginated_response(result_items, final_total, page, page_size)


async def _get_local_assets_count(
        db: AsyncSession,
        name: Optional[str],
        inventory_id: Optional[str],
        serial_number: Optional[str],
        asset_status: Optional[str],
        model_id: Optional[int],
        asset_type_id: Optional[int],
        parent_id: Optional[int],
        employee_id: Optional[str],
) -> int:
    """Подсчет количества локальных активов по всем фильтрам."""
    query = select(func.count(Asset.asset_id))

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
        query = query.where(Asset.asset_id.in_(emp_asset_subq))

    result = await db.execute(query)
    return result.scalar_one() or 0


async def _get_local_assets_slice(
        db: AsyncSession,
        skip: int,
        limit: int,
        name: Optional[str],
        inventory_id: Optional[str],
        serial_number: Optional[str],
        asset_status: Optional[str],
        model_id: Optional[int],
        asset_type_id: Optional[int],
        parent_id: Optional[int],
        employee_id: Optional[str],
) -> Sequence[Asset]:
    """Получение среза локальных активов с полной загрузкой связей."""
    query = select(Asset).options(
        selectinload(Asset.asset_type),
        selectinload(Asset.asset_status),
        selectinload(Asset.model),
        selectinload(Asset.parent).options(
            selectinload(Asset.asset_type),
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
        query = query.where(Asset.asset_id.in_(emp_asset_subq))

    query = query.order_by(Asset.asset_id.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def _fetch_and_merge_sap_assets(
        db: AsyncSession,
        limit: int,
        offset: int,
        name: Optional[str],
        inventory_id: Optional[str],
        serial_number: Optional[str],
        employee_id: Optional[str],
        search_mode: str,
        exclude_inventory_ids: List[str],
) -> Tuple[List[Dict[str, Any]], int]:
    """Запрос к SAP и слияние с исключением дубликатов."""
    try:
        sap_response = await _fetch_sap_materials(
            page=1, # Мы управляем пагинацией через limit/offset вручную
            page_size=limit,
            search_mode=search_mode,
            base_material_name_like=name,
            inventory_number=inventory_id,
            serial_number=serial_number,
            employee_id=employee_id,
            # Если ваш SAP API поддерживает параметр исключения, раскомментируйте и передайте его:
            # exclude_inventory_numbers=",".join(exclude_inventory_ids) if exclude_inventory_ids else None
        )

        if not sap_response.get("success") or "data" not in sap_response.get("response", {}):
            return [], 0

        sap_data = sap_response["response"]
        sap_items_raw = sap_data.get("data", [])
        sap_total = sap_data.get("total", 0)

        # Фильтрация дубликатов в Python (если SAP API не поддерживает exclude)
        filtered_sap_items = []
        employee_ids = set()
        department_codes = set()

        for item in sap_items_raw:
            if item.get("inventory_number") in exclude_inventory_ids:
                continue
            filtered_sap_items.append(item)

            if item.get("employee_id"):
                employee_ids.add("00" + item["employee_id"])
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

        # Сборка виртуальных активов
        virtual_assets = []
        for sap_item in filtered_sap_items:
            virtual_assets.append(_build_virtual_asset(sap_item, employees_map, departments_map))

        return virtual_assets, sap_total

    except Exception as e:
        logger.error(f"[SAP FALLBACK] Ошибка при запросе к SAP API: {e}", exc_info=True)
        return [], 0


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

    users = []
    if employee:
        users.append(_build_user_response(employee, "user"))

    current_user_full_name = None
    if employee:
        parts = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
        current_user_full_name = " ".join(parts) if parts else None

    raw_material_id = sap_item.get("material_id")
    if raw_material_id is not None:
        try:
            asset_id_val = int(raw_material_id)
        except (ValueError, OverflowError):
            asset_id_val = zlib.crc32(str(raw_material_id).encode()) & 0x7FFFFFFF
    else:
        inv = str(sap_item.get("inventory_number", ""))
        serial = str(sap_item.get("serial_number", ""))
        asset_id_val = zlib.crc32(f"{inv}_{serial}".encode()) & 0x7FFFFFFF

    return {
        # "asset_id": asset_id_val,
        "asset_id": None,
        "name": sap_item.get("base_material_name"),
        "inventory_id": sap_item.get("inventory_number"),
        "serial_number": sap_item.get("serial_number"),
        "quantity": int(sap_item.get("quantity", 0)) if sap_item.get("quantity") is not None else 0,
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
        "created_at": None,
        "updated_at": None,
        "asset_type_name": None,
        "location": None,
        "users": users,
        "responsible_users": [],
        "serving_users": [],
        "current_user": raw_employee_id,
        "current_user_full_name": current_user_full_name,
        "parent": None,
        "material_id": raw_material_id
    }


def _build_user_response(employee: Employee, assignment_type: str) -> Dict[str, Any]:
    parts_ru = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
    parts_en = [p for p in [employee.last_name_en, employee.first_name_en, employee.middle_name_en] if p]

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

    # БЕЗОПАСНОЕ чтение атрибутов напрямую из __dict__ для избежания MissingGreenlet
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
        "group": _get_dept_dict(getattr(employee, 'group', None)),
        "position": position_data,
        "start_date": None,
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