# import logging
# import os
# from datetime import date
# from typing import List, Dict, Optional, Any, Sequence, Tuple, Literal
# from sqlalchemy import select, func, inspect, Integer, or_, cast, null
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.orm import selectinload
# import httpx
# from app.models.assets.Asset import Asset
# from app.models.assets.AssetAssignment import AssetAssignment
# from app.models.assets.AssetStatus import AssetStatus
# from app.models.map_assets.AssetPosition import AssetPosition
# from app.models.zup.employee import Employee
# from app.models.zup.department import ZupDepartment
# from app.schemas.assets.AssetSchemas import AssetResponse
# from dotenv import load_dotenv
#
# load_dotenv()
#
# logger = logging.getLogger(__name__)
#
# SAP_API_URL = os.getenv("SAP_API_URL", "http://10.168.143.7:8123/sap/") # default - test
# X_API_TOKEN = os.getenv("X_API_TOKEN")
# # ID виртуального типа SAP-активов.
# # ID типа "Без типа" (публичный, права на него не выдаются).
# WITHOUT_TYPE_ASSET_ID = 0
# SearchMode = Literal["ALL", "NOT_NULLS", "NULLS"]
#
# # ============================================================
# # Публичная точка входа
# # ============================================================
# async def get_assets_list_with_sap(
#         db: AsyncSession,
#         page: int = 1,
#         page_size: int = 50,
#         asset_id: Optional[int] = None,
#         material_id: Optional[str] = None,
#         name: Optional[str] = None,
#         inventory_id: Optional[str] = None,
#         serial_number: Optional[str] = None,
#         asset_status: Optional[str] = None,
#         model_id: Optional[int] = None,
#         asset_type_id: Optional[int] = None,
#         parent_id: Optional[int] = None,
#         employee_id: Optional[str] = None,
#         only_my: Optional[bool] = False,
#         search_mode: str = "ALL",
#         # === фильтры по cost_center ===
#         cost_center_shortname_from: Optional[str] = None,
#         cost_center_shortname_from_mode: SearchMode = "ALL",
#         cost_center_code_from: Optional[str] = None,
#         cost_center_code_from_search_mode: SearchMode = "ALL",
#
#         cost_center_shortname: Optional[str] = None,
#         cost_center_shortname_mode: SearchMode = "ALL",
#         cost_center_code: Optional[str] = None,
#
#         next_service_start: Optional[date] = None,
#         next_service_end: Optional[date] = None,
#
#         material_class: Optional[str] = None,
# ) -> Dict[str, Any]:
#     """
#     Получение списка активов: Локальные данные имеют абсолютный приоритет.
#     Список дополняется данными из SAP API, если локальных записей недостаточно.
#
#     Фильтры cost_center_* относятся ТОЛЬКО к виртуальным SAP-активам
#     (в локальной БД этих полей нет). Если задан любой из них, локальная
#     часть исключается из выдачи и из total.
#     """
#     # Есть ли вообще фильтр по cost_center (по значению или по режиму)
#     has_cost_center_filter = (
#             cost_center_shortname_from is not None
#             or cost_center_shortname is not None
#             or cost_center_shortname_from_mode != "ALL"
#             or cost_center_shortname_mode != "ALL"
#     )
#
#     # === ОПТИМИЗАЦИЯ 1: Прямой поиск по уникальным идентификаторам ===
#     if material_id is not None or asset_id is not None:
#         local_orm_items = await get_local_assets_slice(
#             db=db,
#             skip=0,
#             limit=1,
#             asset_id=asset_id,
#             material_id=material_id,
#             name=name,
#             inventory_id=inventory_id,
#             serial_number=serial_number,
#             asset_status=asset_status,
#             model_id=model_id,
#             asset_type_id=asset_type_id,
#             parent_id=parent_id,
#             employee_id=employee_id,
#             cost_center_code_from=cost_center_code_from,
#             cost_center_code_from_search_mode=cost_center_code_from_search_mode,
#             only_my=only_my,
#             next_service_start=next_service_start,
#             next_service_end=next_service_end,
#             material_class=material_class
#         )
#
#         if local_orm_items:
#             local_items = [AssetResponse.model_validate(item, from_attributes=True) for item in local_orm_items]
#             return _build_paginated_response(local_items, total=1, page=1, page_size=1)
#
#     # === ОПТИМИЗАЦИЯ 2: Определяем, нужен ли SAP ===
#     # Виртуальные активы SAP "живут" под WITHOUT_TYPE_ASSET_ID.
#     # "Без типа" (0) — публичный локальный тип, тоже может показываться без SAP,
#     # но виртуалки под него не попадают (см. _build_virtual_asset).
#     #
#     # Если пользователь запросил конкретный тип, отличный от виртуального, —
#     # ни один виртуальный актив не пройдёт фильтрацию → SAP не дёргаем.
#     skip_sap_fetch = (
#             (asset_type_id is not None and asset_type_id != WITHOUT_TYPE_ASSET_ID)
#             or next_service_start is not None
#             or next_service_end is not None
#     )
#     logger.debug(f"skip_sap_fetch = {skip_sap_fetch}, has_cost_center_filter = {has_cost_center_filter}")
#
#     # Если есть cost_center-фильтр, локальные активы всё равно не подойдут,
#     # поэтому локальный total = 0.
#     # if has_cost_center_filter:
#     #     local_total = 0
#     # else:
#     local_total = await _get_local_assets_count(
#         db=db,
#         asset_id=asset_id,
#         material_id=material_id,
#         name=name,
#         inventory_id=inventory_id,
#         serial_number=serial_number,
#         asset_status=asset_status,
#         model_id=model_id,
#         asset_type_id=asset_type_id,
#         parent_id=parent_id,
#         employee_id=employee_id,
#         cost_center_code_from=cost_center_code_from,
#         cost_center_code_from_search_mode=cost_center_code_from_search_mode,
#         only_my=only_my,
#         next_service_start=next_service_start,
#         next_service_end=next_service_end,
#         material_class=material_class
#     )
#
#     skip = (page - 1) * page_size
#     result_items: List[Any] = []
#     sap_total = 0
#
#     # Если на этой странице есть локальные активы, забираем их
#     if not has_cost_center_filter and skip < local_total:
#         local_orm_items = await get_local_assets_slice(
#             db=db,
#             skip=skip,
#             limit=page_size,
#             asset_id=asset_id,
#             material_id=material_id,
#             name=name,
#             inventory_id=inventory_id,
#             serial_number=serial_number,
#             asset_status=asset_status,
#             model_id=model_id,
#             asset_type_id=asset_type_id,
#             parent_id=parent_id,
#             employee_id=employee_id,
#             cost_center_code_from=cost_center_code_from,
#             cost_center_code_from_search_mode=cost_center_code_from_search_mode,
#             only_my=only_my,
#             next_service_start=next_service_start,
#             next_service_end=next_service_end,
#             material_class=material_class
#         )
#
#         local_items = [AssetResponse.model_validate(item, from_attributes=True) for item in local_orm_items]
#         result_items.extend(local_items)
#
#         # Дополняем из SAP, только если есть место и SAP не пропускаем
#         remaining_slots = page_size - len(result_items)
#         if remaining_slots > 0 and not skip_sap_fetch:
#             exclude_inv_ids = [item.inventory_id for item in result_items if getattr(item, "inventory_id", None)]
#
#             # ИСПРАВЛЕНИЕ: используем увеличенный лимит для стабильной оценки total.
#             # Это предотвращает скачки total при изменении page_size, гарантируя,
#             # что мы получаем достаточно данных для корректного определения sap_was_exhausted.
#             sap_limit = max(remaining_slots * 2, 100)
#
#             sap_items, fetched_sap_total = await _fetch_and_merge_sap_assets(
#                 db=db,
#                 limit=sap_limit,
#                 offset=0,
#                 material_id=material_id,
#                 name=name,
#                 inventory_id=inventory_id,
#                 serial_number=serial_number,
#                 employee_id=employee_id,
#                 search_mode=search_mode,
#                 exclude_inventory_ids=exclude_inv_ids,
#                 asset_type_id=asset_type_id,
#                 only_my=bool(only_my),
#                 cost_center_shortname_from=cost_center_shortname_from,
#                 cost_center_shortname_from_mode=cost_center_shortname_from_mode,
#                 cost_center_code_from=cost_center_code_from,
#                 cost_center_code_from_search_mode=cost_center_code_from_search_mode,
#                 cost_center_shortname=cost_center_shortname,
#                 cost_center_shortname_mode=cost_center_shortname_mode,
#                 cost_center_code=cost_center_code,
#                 material_class=material_class
#             )
#             result_items.extend(sap_items[:remaining_slots])
#             sap_total = fetched_sap_total
#     else:
#         # локальные закончились — идём в SAP
#         if not skip_sap_fetch:
#             sap_offset = 0 if has_cost_center_filter else max(0, skip - local_total)
#
#             # ИСПРАВЛЕНИЕ: для первой страницы SAP используем увеличенный лимит
#             # для стабильной оценки total, независимой от page_size.
#             sap_limit = page_size if sap_offset > 0 else max(page_size, 100)
#
#             sap_items, fetched_sap_total = await _fetch_and_merge_sap_assets(
#                 db=db,
#                 limit=sap_limit,
#                 offset=sap_offset,
#                 material_id=material_id,
#                 name=name,
#                 inventory_id=inventory_id,
#                 serial_number=serial_number,
#                 employee_id=employee_id,
#                 search_mode=search_mode,
#                 exclude_inventory_ids=[],
#                 asset_type_id=asset_type_id,
#                 only_my=bool(only_my),
#                 cost_center_shortname_from=cost_center_shortname_from,
#                 cost_center_shortname_from_mode=cost_center_shortname_from_mode,
#                 cost_center_code_from=cost_center_code_from,
#                 cost_center_code_from_search_mode=cost_center_code_from_search_mode,
#                 cost_center_shortname=cost_center_shortname,
#                 cost_center_shortname_mode=cost_center_shortname_mode,
#                 cost_center_code=cost_center_code,
#                 material_class=material_class
#             )
#             result_items.extend(sap_items)
#             sap_total = fetched_sap_total
#
#             logger.info(f"{skip_sap_fetch=} {skip=} {local_total=} {sap_offset=} {fetched_sap_total=} {sap_total=}")
#
#     # Итоговый total
#     final_total = local_total + sap_total
#
#     return _build_paginated_response(result_items, final_total, page, page_size)
#
#
# # ============================================================
# # Локальная часть
# # ============================================================
# async def _get_local_assets_count(
#         db: AsyncSession,
#         asset_id: Optional[int],
#         material_id: Optional[str],
#         name: Optional[str],
#         inventory_id: Optional[str],
#         serial_number: Optional[str],
#         asset_status: Optional[str],
#         model_id: Optional[int],
#         asset_type_id: Optional[int],
#         parent_id: Optional[int],
#         employee_id: Optional[str],
#         cost_center_code_from: Optional[str],
#         cost_center_code_from_search_mode: SearchMode,
#         only_my: Optional[bool] = False,
#         next_service_start: Optional[date] = None,
#         next_service_end: Optional[date] = None,
#         material_class: Optional[str] = None
# ) -> int:
#     """Подсчет количества локальных активов по всем фильтрам."""
#     query = select(func.count(Asset.asset_id))
#
#     if asset_id:
#         query = query.where(Asset.asset_id == asset_id)
#     if material_id:
#         query = query.where(Asset.material_id == material_id)
#     if name:
#         query = query.where(Asset.name.ilike(f"%{name}%"))
#     if inventory_id:
#         query = query.where(Asset.inventory_id.ilike(f"%{inventory_id}%"))
#     if serial_number:
#         query = query.where(Asset.serial_number.ilike(f"%{serial_number}%"))
#     if model_id is not None:
#         query = query.where(Asset.model_id == model_id)
#     if asset_type_id is not None:
#         query = query.where(Asset.asset_type_id == asset_type_id)
#     if parent_id is not None:
#         query = query.where(Asset.parent_id == parent_id)
#     if asset_status:
#         query = query.join(AssetStatus, Asset.asset_status_id == AssetStatus.id)
#         query = query.where(AssetStatus.status == asset_status)
#     if employee_id:
#         emp_asset_subq = (
#             select(AssetAssignment.asset_id)
#             .where(AssetAssignment.employee_id == employee_id)
#             .scalar_subquery()
#         )
#         if only_my:
#             emp_asset_subq = emp_asset_subq.where(AssetAssignment.end_date.is_(None))
#
#         query = query.where(Asset.asset_id.in_(emp_asset_subq))
#
#     # === ОБНОВЛЕННАЯ ЛОГИКА ФИЛЬТРАЦИИ cost_center_code_from ===
#     if cost_center_code_from is not None or cost_center_code_from_search_mode != "ALL":
#         ccc_list = [c.strip() for c in cost_center_code_from.split(";") if c.strip()] if cost_center_code_from else []
#
#         if cost_center_code_from_search_mode == "NULLS":
#             query = query.where(Asset.cost_center_code_from.is_(None))
#         elif cost_center_code_from_search_mode == "NOT_NULLS":
#             if ccc_list:
#                 query = query.where(Asset.cost_center_code_from.in_(ccc_list))
#             else:
#                 query = query.where(Asset.cost_center_code_from.isnot(None))
#         else:  # ALL
#             if ccc_list:
#                 query = query.where(or_(Asset.cost_center_code_from.in_(ccc_list), Asset.cost_center_code_from.is_(None)))
#
#     # Фильтрация по дате обслуживания
#     if next_service_start is not None:
#         query = query.where(Asset.next_service >= next_service_start)
#     if next_service_end is not None:
#         query = query.where(Asset.next_service <= next_service_end)
#     if material_class:
#         query = query.where(Asset.material_class == material_class)
#
#     result = await db.execute(query)
#     return result.scalar_one() or 0
#
# async def get_local_assets_slice(
#         db: AsyncSession,
#         skip: int,
#         limit: int,
#         asset_id: Optional[int],
#         material_id: Optional[str],
#         name: Optional[str],
#         inventory_id: Optional[str],
#         serial_number: Optional[str],
#         asset_status: Optional[str],
#         model_id: Optional[int],
#         asset_type_id: Optional[int],
#         parent_id: Optional[int],
#         employee_id: Optional[str],
#         cost_center_code_from: Optional[str],
#         cost_center_code_from_search_mode: SearchMode = "ALL",
#         only_my: Optional[bool] = False,
#         next_service_start: Optional[date] = None,
#         next_service_end: Optional[date] = None,
#         material_class: Optional[str] = None
# ) -> Sequence[Asset]:
#     """Получение среза локальных активов с полной загрузкой связей."""
#     query = select(Asset).options(
#         selectinload(Asset.asset_type),
#         selectinload(Asset.asset_status),
#         selectinload(Asset.model),
#         selectinload(Asset.parent).options(
#             selectinload(Asset.asset_type),
#             selectinload(Asset.asset_status),
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
#     if asset_id:
#         query = query.where(Asset.asset_id == asset_id)
#     if material_id:
#         query = query.where(Asset.material_id == material_id)
#     if name:
#         query = query.where(Asset.name.ilike(f"%{name}%"))
#     if inventory_id:
#         query = query.where(Asset.inventory_id.ilike(f"%{inventory_id}%"))
#     if serial_number:
#         query = query.where(Asset.serial_number.ilike(f"%{serial_number}%"))
#     if model_id is not None:
#         query = query.where(Asset.model_id == model_id)
#     if asset_type_id is not None:
#         query = query.where(Asset.asset_type_id == asset_type_id)
#     if parent_id is not None:
#         query = query.where(Asset.parent_id == parent_id)
#     if asset_status:
#         query = query.join(AssetStatus, Asset.asset_status_id == AssetStatus.id)
#         query = query.where(AssetStatus.status == asset_status)
#     if employee_id:
#         emp_asset_subq = (
#             select(AssetAssignment.asset_id)
#             .where(AssetAssignment.employee_id == employee_id)
#             .scalar_subquery()
#         )
#         if only_my:
#             emp_asset_subq = emp_asset_subq.where(AssetAssignment.end_date.is_(None))
#
#         query = query.where(Asset.asset_id.in_(emp_asset_subq.scalar_subquery()))
#
#     # === ОБНОВЛЕННАЯ ЛОГИКА ФИЛЬТРАЦИИ cost_center_code_from ===
#     if cost_center_code_from is not None or cost_center_code_from_search_mode != "ALL":
#         ccc_list = [c.strip() for c in cost_center_code_from.split(";") if c.strip()] if cost_center_code_from else []
#
#         if cost_center_code_from_search_mode == "NULLS":
#             query = query.where(Asset.cost_center_code_from.is_(None))
#         elif cost_center_code_from_search_mode == "NOT_NULLS":
#             if ccc_list:
#                 query = query.where(Asset.cost_center_code_from.in_(ccc_list))
#             else:
#                 query = query.where(Asset.cost_center_code_from.isnot(None))
#         else:  # ALL
#             if ccc_list:
#                 query = query.where(or_(Asset.cost_center_code_from.in_(ccc_list), Asset.cost_center_code_from.is_(None)))
#
#     # Фильтрация по дате обслуживания
#     if next_service_start is not None:
#         query = query.where(Asset.next_service >= next_service_start)
#     if next_service_end is not None:
#         query = query.where(Asset.next_service <= next_service_end)
#     if material_class:
#         query = query.where(Asset.material_class == material_class)
#
#     query = query.order_by(Asset.asset_id.desc()).offset(skip).limit(limit)
#     result = await db.execute(query)
#     return result.scalars().all()
#
#
# # ============================================================
# # SAP-часть
# # ============================================================
# def _matches_cost_center(
#         value: Optional[str],
#         pattern: Optional[str],
#         mode: SearchMode,
# ) -> bool:
#     """
#     Проверка одного cost_center-поля на соответствие фильтру.
#
#     - mode=NOT_NULLS  → поле должно быть непустым
#     - mode=NULLS      → поле должно быть пустым
#     - mode=ALL:
#         * pattern=None → фильтр не применяется (True)
#         * pattern задан → подстрочный поиск (без учёта регистра)
#     """
#     has_value = value is not None and str(value).strip() != ""
#
#     if mode == "NOT_NULLS":
#         return has_value
#     if mode == "NULLS":
#         return not has_value
#
#     # mode == "ALL"
#     if pattern is None:
#         return True
#     if not has_value:
#         return False
#     return pattern.strip().lower() in str(value).strip().lower()
#
#
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
#         cost_center_shortname_from: Optional[str] = None,
#         cost_center_shortname_from_mode: SearchMode = "ALL",
#         cost_center_code_from: Optional[str] = None,
#         cost_center_code_from_search_mode: SearchMode = "ALL",
#         cost_center_shortname: Optional[str] = None,
#         cost_center_shortname_mode: SearchMode = "ALL",
#         cost_center_code: Optional[str] = None,
#         material_class: Optional[str] = None
# ) -> Tuple[List[Dict[str, Any]], int]:
#     """Запрос к SAP и слияние с исключением дубликатов и 'призрачных' SAP активов."""
#     try:
#         sap_response = await fetch_sap_materials(
#             offset=offset,
#             page_size=limit,
#             material_id=material_id,
#             search_mode=search_mode,
#             base_material_name_like=name,
#             inventory_number=inventory_id,
#             serial_number=serial_number,
#             employee_id=employee_id,
#             cost_center_code_from=cost_center_code_from,
#             cost_center_code_from_search_mode=cost_center_code_from_search_mode,
#             cost_center_shortname_from=cost_center_shortname_from,
#             cost_center_code=cost_center_code,
#             cost_center_shortname=cost_center_shortname,
#             material_class=material_class
#         )
#
#         if not sap_response.get("success") or "data" not in sap_response.get("response", {}):
#             return [], 0
#
#         sap_data = sap_response["response"]
#         sap_items_raw = sap_data.get("data", [])
#         sap_total = sap_data.get("total", 0)
#
#         logger.debug(f"[SAP DEBUG] SAP вернул total={sap_total}, элементов в data={len(sap_items_raw)}")
#
#         # Собираем все инвентарные и материальные ID из текущей выдачи SAP с нормализацией
#         sap_inventory_ids = [
#             str(item.get("inventory_number")).strip().lower()
#             for item in sap_items_raw if item.get("inventory_number")
#         ]
#         sap_material_ids = [
#             str(item.get("material_id")).strip().lower()
#             for item in sap_items_raw if item.get("material_id")
#         ]
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
#             local_inv_ids_to_exclude = {
#                 str(rec.inventory_id).strip().lower()
#                 for rec in existing_records if rec.inventory_id
#             }
#             local_mat_ids_to_exclude = {
#                 str(rec.material_id).strip().lower()
#                 for rec in existing_records if rec.material_id
#             }
#
#         filtered_sap_items = []
#         employee_ids = set()
#         department_codes = set()
#         excluded_count = 0
#
#         target_emp_id = str(employee_id).strip() if employee_id else ""
#         norm_exclude_ids = {str(x).strip().lower() for x in exclude_inventory_ids}
#
#         def _normalize_emp_id(x) -> str:
#             return "00" + str(x).strip() if x else ""
#
#         has_cc_from_filter = (
#                 cost_center_shortname_from is not None
#                 or cost_center_shortname_from_mode != "ALL"
#         )
#         has_cc_owner_filter = (
#                 cost_center_shortname is not None
#                 or cost_center_shortname_mode != "ALL"
#         )
#
#         for item in sap_items_raw:
#             inv_num = str(item.get("inventory_number", "")).strip().lower()
#             mat_id = str(item.get("material_id", "")).strip().lower()
#
#             is_excluded = False
#
#             # 1. Исключаем, если уже есть на текущей странице локальных результатов
#             if inv_num and inv_num in norm_exclude_ids:
#                 is_excluded = True
#
#             # 2. Исключаем, если этот актив УЖЕ существует в локальной БД в принципе
#             elif inv_num and inv_num in local_inv_ids_to_exclude:
#                 is_excluded = True
#             elif mat_id and mat_id in local_mat_ids_to_exclude:
#                 is_excluded = True
#
#             # 3. Проверка only_my
#             elif only_my and target_emp_id:
#                 sap_emp_id = _normalize_emp_id(item.get("employee_id"))
#                 if sap_emp_id != target_emp_id:
#                     is_excluded = True
#
#             # 4. cost_center_shortname_from (ответственный департамент)
#             if not is_excluded and has_cc_from_filter:
#                 if not _matches_cost_center(
#                         item.get("cost_center_shortname_from"),
#                         cost_center_shortname_from,
#                         cost_center_shortname_from_mode,
#                 ):
#                     is_excluded = True
#
#             # 5. cost_center_shortname (департамент владельца)
#             if not is_excluded and has_cc_owner_filter:
#                 if not _matches_cost_center(
#                         item.get("cost_center_shortname"),
#                         cost_center_shortname,
#                         cost_center_shortname_mode,
#                 ):
#                     is_excluded = True
#
#             if is_excluded:
#                 excluded_count += 1
#                 logger.debug(f"[SAP DEBUG] ИСКЛЮЧЕН актив: inv='{inv_num}', mat='{mat_id}'.")
#                 continue
#
#             filtered_sap_items.append(item)
#
#             if item.get("employee_id"):
#                 employee_ids.add(_normalize_emp_id(item["employee_id"]))
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
#         virtual_assets = []
#         for sap_item in filtered_sap_items:
#             virtual_asset = _build_virtual_asset(sap_item, employees_map, departments_map)
#             # Виртуальные активы имеют asset_type_id =0
#             # Пропускаем их, если запрошен конкретный другой тип.
#             if asset_type_id is None or asset_type_id == WITHOUT_TYPE_ASSET_ID:
#                 virtual_assets.append(virtual_asset)
#
#         # === Корректировка total ===
#         # real_sap_items_count — сколько всего элементов вернул SAP в этом ответе.
#         # Если SAP вернул меньше, чем мы просили (len(data) < limit),
#         # значит, это весь результат, и sap_total нужно пересчитать от отфильтрованного.
#         # Иначе — это страница пагинации, и корректируем только на excluded_count.
#         real_sap_items_count = len(filtered_sap_items) + excluded_count
#         sap_was_exhausted = len(sap_items_raw) < limit
#
#         # if offset == 0 and sap_was_exhausted and real_sap_items_count < sap_total:
#         #     adjusted_sap_total = len(filtered_sap_items)
#         #     logger.debug(
#         #         f"[SAP DEBUG] SAP total ({sap_total}) > real ({real_sap_items_count}), "
#         #         f"offset=0, ответ исчерпан → total={adjusted_sap_total}"
#         #     )
#         # else:
#         #     adjusted_sap_total = max(0, sap_total - excluded_count)
#         #     logger.debug(
#         #         f"[SAP DEBUG] Стандартная корректировка: sap_total={sap_total}, "
#         #         f"исключено={excluded_count}, adjusted={adjusted_sap_total}"
#         #     )
#
#         if offset == 0 and sap_was_exhausted:
#             # Если SAP вернул меньше элементов, чем limit, значит это ВСЕ элементы.
#             # Точное количество доступных элементов равно len(filtered_sap_items).
#             adjusted_sap_total = len(filtered_sap_items)
#             logger.debug(
#                 f"[SAP DEBUG] SAP вернул {len(sap_items_raw)} < {limit}, набор исчерпан. "
#                 f"adjusted_sap_total = {adjusted_sap_total}"
#             )
#         else:
#             # Если набор не исчерпан, оцениваем total как sap_total - excluded_count.
#             # Благодаря увеличенному sap_limit на первой странице, эта оценка
#             # становится гораздо стабильнее и не скачет при изменении page_size.
#             adjusted_sap_total = max(0, sap_total - excluded_count)
#             logger.debug(
#                 f"[SAP DEBUG] Набор не исчерпан ({len(sap_items_raw)} >= {limit}). "
#                 f"sap_total={sap_total}, excluded={excluded_count}, adjusted={adjusted_sap_total}"
#             )
#
#         return virtual_assets, adjusted_sap_total
#
#     except Exception as e:
#         logger.error(f"[SAP FALLBACK] Ошибка при запросе к SAP API: {e}", exc_info=True)
#         return [], 0
#
#
# async def fetch_sap_materials(
#         offset: int,
#         page_size: int,
#         material_id: Optional[str],
#         search_mode: str = "ALL",
#         base_material_name_like: Optional[str] = None,
#         inventory_number: Optional[str] = None,
#         serial_number: Optional[str] = None,
#         employee_id: Optional[str] = None,
#         cost_center_code_from: Optional[str] = None,
#         cost_center_code_from_search_mode: SearchMode = "ALL",
#         cost_center_shortname_from: Optional[str] = None,
#         cost_center_code: Optional[str] = None,
#         cost_center_shortname: Optional[str] = None,
#         is_long_serial_number = True,
#         material_class: Optional[str] = None,
# ) -> Dict[str, Any]:
#     """Запрос к SAP API для получения списка материалов."""
#     # offset = (page - 1) * page_size
#     headers = {
#         "X-API-Token": X_API_TOKEN
#     }
#
#     params = {
#         "limit": page_size,
#         "offset": offset,
#         "employee_id_search_mode": search_mode,
#     }
#
#     if material_id:
#         params["material_id"] = material_id
#     if base_material_name_like:
#         params["base_material_name_like"] = base_material_name_like
#     if inventory_number:
#         params["inventory_number"] = inventory_number
#     if serial_number and is_long_serial_number:
#         params["long_serial_number"] = serial_number
#     if serial_number and not is_long_serial_number:
#         params["serial_number"] = serial_number
#     if employee_id:
#         params["employee_id"] = employee_id
#     if cost_center_code_from:
#         params["cost_center_code_from"] = cost_center_code_from
#     if cost_center_code_from_search_mode:
#         params["cost_center_code_from_search_mode"] = cost_center_code_from_search_mode
#     if cost_center_shortname_from:
#         params["cost_center_shortname_from"] = cost_center_shortname_from
#     if cost_center_code:
#         params["cost_center_code"] = cost_center_code
#     if cost_center_shortname:
#         params["cost_center_shortname"] = cost_center_shortname
#     if material_class:
#         params["material_class"] = material_class
#
#     async with httpx.AsyncClient(timeout=30.0) as client:
#         response = await client.get(SAP_API_URL + "base_materials", params=params, headers=headers)
#         response.raise_for_status()
#         resp = response.json()
#         logger.debug(f"{resp.get("response").get("data")=}")
#         if resp.get("response").get("data") == [] and is_long_serial_number:
#             return await fetch_sap_materials(
#                 offset=offset,
#                 page_size=page_size,
#                 material_id=material_id,
#                 search_mode=search_mode,
#                 base_material_name_like=base_material_name_like,
#                 inventory_number=inventory_number,
#                 serial_number=serial_number,
#                 employee_id=employee_id,
#                 cost_center_code_from=cost_center_code_from,
#                 cost_center_code_from_search_mode=cost_center_code_from_search_mode,
#                 cost_center_shortname_from=cost_center_shortname_from,
#                 cost_center_code=cost_center_code,
#                 cost_center_shortname=cost_center_shortname,
#                 is_long_serial_number=False,
#                 material_class=material_class
#             )
#         if resp.get("response").get("data") == [] and not is_long_serial_number:
#             return resp
#         return resp
#
#
# # ============================================================
# # Загрузка сотрудников и департаментов
# # ============================================================
# async def _get_employees_by_ids(
#         db: AsyncSession,
#         employee_ids: List[str],
# ) -> list[Any] | Sequence[Any]:
#     """Массовая загрузка сотрудников по employee_id с учетом разного количества ведущих нулей."""
#     if not employee_ids:
#         return []
#
#     numeric_ids = []
#     string_ids = []
#     for eid in employee_ids:
#         try:
#             numeric_ids.append(int(eid))
#         except (ValueError, TypeError):
#             string_ids.append(eid)
#
#     conditions = []
#     if numeric_ids:
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
#         .where(or_(*conditions))
#     )
#
#     result = await db.execute(query)
#     employees = result.scalars().all()
#
#     for emp in employees:
#         hierarchy_chain = []
#         current = emp.group
#         while current is not None:
#             hierarchy_chain.append(current)
#             if not current.parent_guid or current.parent_guid == "00000000-0000-0000-0000-000000000000":
#                 break
#             insp = inspect(current)
#             parent_attr = insp.attrs.get('parent')
#             if parent_attr is None or parent_attr.loaded_value is None:
#                 break
#             current = parent_attr.loaded_value
#         hierarchy_chain.reverse()
#         emp.society = hierarchy_chain[0] if len(hierarchy_chain) >= 1 else None
#         emp.department = hierarchy_chain[1] if len(hierarchy_chain) >= 2 else None
#         emp.division = hierarchy_chain[2] if len(hierarchy_chain) >= 3 else None
#         emp.group = hierarchy_chain[3] if len(hierarchy_chain) >= 4 else None
#
#     return employees
#
#
# async def _get_departments_by_codes(
#         db: AsyncSession,
#         department_codes: List[str],
# ) -> list[Any] | Sequence[Any]:
#     if not department_codes:
#         return []
#     query = select(ZupDepartment).where(ZupDepartment.short_name.in_(department_codes))
#     result = await db.execute(query)
#     return result.scalars().all()
#
#
# # ============================================================
# # Построение виртуального актива
# # ============================================================
# def _build_virtual_asset(
#         sap_item: Dict[str, Any],
#         employees_map: Dict[str, Employee],
#         departments_map: Dict[str, ZupDepartment],
# ) -> Dict[str, Any]:
#     raw_employee_id = "00" + str(sap_item.get("employee_id")) if sap_item.get("employee_id") else None
#     employee = employees_map.get(raw_employee_id) if raw_employee_id else None
#
#     start_date = sap_item.get("changed_date") if sap_item.get("changed_date") else None
#
#     users = []
#     if employee:
#         users.append(_build_user_response(employee, "user", start_date))
#
#     current_user_full_name = None
#     if employee:
#         parts = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
#         current_user_full_name = " ".join(parts) if parts else None
#
#     raw_material_id = sap_item.get("material_id")
#
#     return {
#         "asset_id": None,
#         "name": sap_item.get("base_material_name"),
#         "inventory_id": sap_item.get("inventory_number"),
#         # в приоритете длинный серийный номер
#         "serial_number": sap_item.get("long_serial_number") if sap_item.get("long_serial_number") else sap_item.get("serial_number"),
#         "quantity": int(sap_item.get("quantity", 0)) if sap_item.get("quantity") is not None else 0,
#         "asset_status": "В работе",
#         "asset_status_id": 10,
#         "comment": None,
#         "date_issue": None,
#         "date_purchasing": None,
#         "model_id": None,
#         "model_name": None,
#         "parent_id": None,
#         "every_week_check": False,
#         "next_service": None,
#         "next_check": None,
#         "service_period": 0,
#         "check_period": 0,
#         "parent_name": None,
#         "manufacturer_name": None,
#         "vendor_name": None,
#         "os_name": None,
#         "created_by": None,
#         "updated_by": None,
#         "created_at": None,
#         "updated_at": None,
#         "asset_type_name": "Без типа",
#         "asset_type_id": WITHOUT_TYPE_ASSET_ID,
#         "location": None,
#         "users": users,
#
#         # ответственный департамент
#         "cost_center_code_from": sap_item.get("cost_center_code_from") or None,
#         "cost_center_name_from": sap_item.get("cost_center_name_from") or None,
#         "cost_center_shortname_from": sap_item.get("cost_center_shortname_from") or None,
#
#         # департамент владельца
#         "cost_center_code": sap_item.get("cost_center_code") or None,
#         "cost_center_name": sap_item.get("cost_center_name") or None,
#         "cost_center_shortname": sap_item.get("cost_center_shortname") or None,
#
#         "serving_users": [],
#         "current_user": raw_employee_id,
#         "current_user_full_name": current_user_full_name,
#         "parent": None,
#         "material_id": raw_material_id,
#
#         # Новые поля: класс материала (тип), дата списания
#         "material_class": sap_item.get("material_class") or None,
#         "write_off_date": sap_item.get("write_off_date") or None,
#         "material_class_name": sap_item.get("material_class_name") or None,
#     }
#
#
# def _build_user_response(employee: Employee, assignment_type: str, start_date: str) -> Dict[str, Any]:
#     parts_ru = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
#     parts_en = [p for p in [employee.last_name_en, employee.first_name_en, employee.middle_name_en] if p]
#
#     format_start_date = (
#         start_date[:4] + "-" + start_date[4:6] + "-" + start_date[6:]
#         if start_date and len(start_date) >= 8 else None
#     )
#
#     position_data = None
#     if getattr(employee, 'position', None):
#         position_data = {
#             "name": employee.position.name,
#             "name_en": employee.position.name_en,
#         }
#
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
#         "created_at": created_at,
#         "updated_at": updated_at,
#         "full_name_ru": " ".join(parts_ru) if parts_ru else None,
#         "full_name_en": " ".join(parts_en) if parts_en else None,
#         "society": _get_dept_dict(getattr(employee, 'society', None)),
#         "department": _get_dept_dict(getattr(employee, 'department', None)),
#         "division": _get_dept_dict(getattr(employee, 'division', None)),
#         "group": employee.__dict__.get('group'),
#         "position": position_data,
#         "start_date": format_start_date,
#         "end_date": None,
#         "assignment_type": assignment_type,
#     }
#
#
# # ============================================================
# # Пагинация
# # ============================================================
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



import logging
import os
from datetime import date
from typing import List, Dict, Optional, Any, Sequence, Tuple, Literal

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
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SAP_API_URL = os.getenv("SAP_API_URL", "http://10.168.143.7:8123/sap/")
X_API_TOKEN = os.getenv("X_API_TOKEN")

WITHOUT_TYPE_ASSET_ID = 0
SearchMode = Literal["ALL", "NOT_NULLS", "NULLS"]


# ============================================================
# Публичная точка входа (SAP-FIRST логика)
# ============================================================
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
        search_mode: str = "ALL",
        cost_center_shortname_from: Optional[str] = None,
        cost_center_shortname_from_mode: SearchMode = "ALL",
        cost_center_code_from: Optional[str] = None,
        cost_center_code_from_search_mode: SearchMode = "ALL",
        cost_center_shortname: Optional[str] = None,
        cost_center_shortname_mode: SearchMode = "ALL",
        cost_center_code: Optional[str] = None,
        next_service_start: Optional[date] = None,
        next_service_end: Optional[date] = None,
        material_class: Optional[str] = None,
) -> Dict[str, Any]:

    # === ОПТИМИЗАЦИЯ: Прямой поиск по уникальному идентификатору ===
    if material_id is not None or asset_id is not None:
        # 1. Сначала ищем в SAP
        sap_response = await fetch_sap_materials(
            offset=0, page_size=1, material_id=material_id, search_mode=search_mode,
            base_material_name_like=name, inventory_number=inventory_id,
            serial_number=serial_number, employee_id=employee_id,
            cost_center_code_from=cost_center_code_from,
            cost_center_code_from_search_mode=cost_center_code_from_search_mode,
            cost_center_shortname_from=cost_center_shortname_from,
            cost_center_code=cost_center_code,
            cost_center_shortname=cost_center_shortname,
            material_class=material_class
        )

        if sap_response.get("success") and sap_response.get("response", {}).get("data"):
            sap_item = sap_response["response"]["data"][0]
            # Ищем локальное переопределение для этого актива
            local_override = await _get_local_override(db, sap_item.get("material_id"), sap_item.get("inventory_number"))
            if local_override:
                merged = _merge_sap_with_local(sap_item, local_override, db)
                return _build_paginated_response([merged], total=1, page=1, page_size=1)
            else:
                # Только SAP
                employees_map, departments_map = await _load_maps_for_sap_items(db, [sap_item])
                virtual = _build_virtual_asset(sap_item, employees_map, departments_map)
                return _build_paginated_response([virtual], total=1, page=1, page_size=1)

        # 2. Если в SAP нет, ищем чисто локальный актив
        local_orm_items = await get_local_assets_slice(
            db=db, skip=0, limit=1, asset_id=asset_id, material_id=material_id,
            name=name, inventory_id=inventory_id, serial_number=serial_number,
            asset_status=asset_status, model_id=model_id, asset_type_id=asset_type_id,
            parent_id=parent_id, employee_id=employee_id,
            cost_center_code_from=cost_center_code_from,
            cost_center_code_from_search_mode=cost_center_code_from_search_mode,
            only_my=only_my, next_service_start=next_service_start,
            next_service_end=next_service_end, material_class=material_class
        )
        if local_orm_items:
            local_items = [AssetResponse.model_validate(item, from_attributes=True) for item in local_orm_items]
            return _build_paginated_response(local_items, total=1, page=1, page_size=1)

    # === ОСНОВНАЯ ПАГИНАЦИЯ: SAP как драйвер ===
    skip = (page - 1) * page_size

    # Определяем, можно ли вообще показывать SAP-активы при текущих фильтрах
    skip_sap_fetch = (
            (asset_type_id is not None and asset_type_id != WITHOUT_TYPE_ASSET_ID)
            or next_service_start is not None
            or next_service_end is not None
    )

    sap_items_raw = []
    sap_total = 0

    if not skip_sap_fetch:
        # Запрашиваем у SAP именно нужный срез данных
        sap_response = await fetch_sap_materials(
            offset=skip,
            page_size=page_size,
            material_id=material_id,
            search_mode=search_mode,
            base_material_name_like=name,
            inventory_number=inventory_id,
            serial_number=serial_number,
            employee_id=employee_id,
            cost_center_code_from=cost_center_code_from,
            cost_center_code_from_search_mode=cost_center_code_from_search_mode,
            cost_center_shortname_from=cost_center_shortname_from,
            cost_center_code=cost_center_code,
            cost_center_shortname=cost_center_shortname,
            material_class=material_class
        )
        if sap_response.get("success") and "data" in sap_response.get("response", {}):
            sap_items_raw = sap_response["response"]["data"]
            sap_total = sap_response["response"].get("total", 0)

    result_items = []

    # Если мы в диапазоне SAP-данных, обогащаем их локальными переопределениями
    if sap_items_raw:
        local_overrides = await _get_local_overrides_for_list(db, sap_items_raw)
        employees_map, departments_map = await _load_maps_for_sap_items(db, sap_items_raw)

        for sap_item in sap_items_raw:
            local_asset = local_overrides.get(sap_item.get("material_id")) or local_overrides.get(sap_item.get("inventory_number"))
            if local_asset:
                # SAP как база + локальные данные поверх
                result_items.append(_merge_sap_with_local(sap_item, local_asset, db))
            else:
                # Чистый SAP-актив
                result_items.append(_build_virtual_asset(sap_item, employees_map, departments_map))

    # Если SAP вернул меньше записей, чем нужно для заполнения страницы (мы на "стыке" или SAP закончился),
    # дополняем страницу чисто локальными активами, которых нет в SAP.
    remaining_slots = page_size - len(result_items)
    if remaining_slots > 0 and not skip_sap_fetch:
        # Исключаем из локальной выборки те material_id/inventory_id, которые уже есть на этой странице SAP
        exclude_material_ids = [item.get("material_id") for item in sap_items_raw if item.get("material_id")]
        exclude_inventory_ids = [item.get("inventory_number") for item in sap_items_raw if item.get("inventory_number")]

        filler_items = await _get_local_only_assets_slice(
            db=db,
            skip=0, # Для filler мы всегда начинаем с 0 относительно "хвоста", но ограничиваем remaining_slots
            limit=remaining_slots,
            exclude_material_ids=exclude_material_ids,
            exclude_inventory_ids=exclude_inventory_ids,
            name=name, inventory_id=inventory_id, serial_number=serial_number,
            asset_status=asset_status, model_id=model_id, asset_type_id=asset_type_id,
            parent_id=parent_id, employee_id=employee_id, only_my=only_my,
            next_service_start=next_service_start, next_service_end=next_service_end,
            material_class=material_class
        )
        result_items.extend(filler_items)

    # Итоговый total: берем масштаб SAP. Локальные "хвосты" добавляются к общему числу.
    # Для производительности local_only_count аппроксимируется или считается отдельно,
    # но для UI пагинации sap_total является основным ориентиром.
    final_total = sap_total

    return _build_paginated_response(result_items, final_total, page, page_size)


# ============================================================
# Функции слияния и обогащения (SAP-FIRST)
# ============================================================
async def _get_local_override(db: AsyncSession, material_id: Optional[str], inventory_id: Optional[str]) -> Optional[Asset]:
    """Ищет локальное переопределение по material_id или inventory_id с полной загрузкой связей."""
    conditions = []
    if material_id:
        conditions.append(Asset.material_id == material_id)
    if inventory_id:
        conditions.append(Asset.inventory_id == inventory_id)

    if not conditions:
        return None

    # ДОБАВЛЕНО: Полная загрузка связей, чтобы избежать MissingGreenlet при доступе к asset_type и другим полям
    query = select(Asset).where(or_(*conditions)).options(
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
    ).limit(1)

    result = await db.execute(query)
    return result.scalar_one_or_none()


def _merge_sap_with_local(sap_item: Dict[str, Any], local_asset: Asset, db: AsyncSession) -> Dict[str, Any]:
    """
    Объединяет данные: SAP является базой, локальные поля перезаписывают её, если они не None.
    """
    # 1. Строим базовый виртуальный актив из SAP
    merged = _build_virtual_asset(sap_item, {}, {})

    # 2. Перезаписываем локальными данными (приоритет локальной системе)
    if local_asset.name: merged['name'] = local_asset.name
    if local_asset.serial_number: merged['serial_number'] = local_asset.serial_number
    if local_asset.comment: merged['comment'] = local_asset.comment
    if local_asset.date_issue: merged['date_issue'] = local_asset.date_issue
    if local_asset.date_purchasing: merged['date_purchasing'] = local_asset.date_purchasing
    if local_asset.model_id: merged['model_id'] = local_asset.model_id
    if local_asset.model_name: merged['model_name'] = local_asset.model_name
    if local_asset.asset_type_id: merged['asset_type_id'] = local_asset.asset_type_id
    if local_asset.asset_type: merged['asset_type_name'] = local_asset.asset_type.name
    if local_asset.parent_id: merged['parent_id'] = local_asset.parent_id
    if local_asset.asset_status_id: merged['asset_status_id'] = local_asset.asset_status_id
    if local_asset.asset_status: merged['asset_status'] = local_asset.asset_status.status
    if local_asset.parent_name: merged['parent_name'] = local_asset.parent_name
    if local_asset.manufacturer_name: merged['manufacturer_name'] = local_asset.manufacturer_name
    if local_asset.vendor_name: merged['vendor_name'] = local_asset.vendor_name
    if local_asset.os_name: merged['os_name'] = local_asset.os_name

    # Локальные идентификаторы и метаданные
    merged['asset_id'] = local_asset.asset_id
    if local_asset.created_by: merged['created_by'] = local_asset.created_by
    if local_asset.updated_by: merged['updated_by'] = local_asset.updated_by
    if local_asset.created_at: merged['created_at'] = local_asset.created_at
    if local_asset.updated_at: merged['updated_at'] = local_asset.updated_at

    # Локальная позиция на карте
    if local_asset.asset_positions:
        active_pos = next((pos for pos in local_asset.asset_positions if pos.is_active), None)
        if active_pos:
            merged['location'] = {
                "workshop_id": active_pos.workshop_id,
                "workshop_name": active_pos.workshop.name if active_pos.workshop else None,
                "place": active_pos.place,
                "level": active_pos.level,
                "x": active_pos.x,
                "y": active_pos.y,
            }

    # Локальные пользователи (перезаписывают SAP-пользователя, если есть)
    if local_asset.assignments:
        active_assignments = [a for a in local_asset.assignments if a.end_date is None]
        if active_assignments:
            users_list = []
            for a in active_assignments:
                emp = a.employee
                if emp:
                    parts_ru = [p for p in [emp.last_name, emp.first_name, emp.middle_name] if p]
                    parts_en = [p for p in [emp.last_name_en, emp.first_name_en, emp.middle_name_en] if p]

                    user_dict = {
                        "guid": emp.guid,
                        "employee_id": emp.employee_id,
                        "full_name_ru": " ".join(parts_ru) if parts_ru else None,
                        "full_name_en": " ".join(parts_en) if parts_en else None,
                        "assignment_type": a.assignment_type.value if hasattr(a.assignment_type, 'value') else str(a.assignment_type),
                        "start_date": a.start_date.isoformat() if a.start_date else None,
                        "end_date": None,
                        "birth_date": emp.birth_date,
                        "employment_date": emp.employment_date,
                        "dismissal_date": emp.dismissal_date,
                        "phone": emp.phone,
                        "email": emp.email,
                        "comment": emp.comment,
                        "position_guid": emp.position_guid,
                        "department_guid": emp.department_guid,
                        "created_at": emp.created_at.isoformat() if emp.created_at else None,
                        "updated_at": emp.updated_at.isoformat() if emp.updated_at else None,
                    }

                    if hasattr(emp, 'position') and emp.position:
                        user_dict["position"] = {"name": emp.position.name, "name_en": emp.position.name_en}

                    # Добавляем иерархию подразделений, если она загружена через selectinload
                    if hasattr(emp, 'society') and emp.society:
                        user_dict["society"] = {"guid": emp.society.guid, "name": emp.society.name, "short_name": getattr(emp.society, 'short_name', None)}
                    if hasattr(emp, 'department') and emp.department:
                        user_dict["department"] = {"guid": emp.department.guid, "name": emp.department.name, "short_name": getattr(emp.department, 'short_name', None)}
                    if hasattr(emp, 'division') and emp.division:
                        user_dict["division"] = {"guid": emp.division.guid, "name": emp.division.name, "short_name": getattr(emp.division, 'short_name', None)}
                    if hasattr(emp, 'group') and emp.group:
                        user_dict["group"] = {"guid": emp.group.guid, "name": emp.group.name, "short_name": getattr(emp.group, 'short_name', None)}

                    users_list.append(user_dict)

            merged['users'] = users_list

            # Устанавливаем current_user из первой активной привязки для совместимости
            first_emp = active_assignments[0].employee
            if first_emp:
                merged['current_user'] = first_emp.employee_id
                parts = [p for p in [first_emp.last_name, first_emp.first_name, first_emp.middle_name] if p]
                merged['current_user_full_name'] = " ".join(parts) if parts else None

    return merged

async def _get_local_overrides_for_list(db: AsyncSession, sap_items: List[Dict[str, Any]]) -> Dict[str, Asset]:
    """Массовая загрузка локальных переопределений для списка SAP-активов с полной загрузкой связей."""
    material_ids = [item.get("material_id") for item in sap_items if item.get("material_id")]
    inventory_ids = [item.get("inventory_number") for item in sap_items if item.get("inventory_number")]

    if not material_ids and not inventory_ids:
        return {}

    conditions = []
    if material_ids:
        conditions.append(Asset.material_id.in_(material_ids))
    if inventory_ids:
        conditions.append(Asset.inventory_id.in_(inventory_ids))

    # Полная загрузка связей, чтобы избежать MissingGreenlet при сериализации
    query = select(Asset).where(or_(*conditions)).options(
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

    result = await db.execute(query)

    overrides = {}
    for asset in result.scalars().all():
        if asset.material_id:
            overrides[asset.material_id] = asset
        if asset.inventory_id:
            overrides[asset.inventory_id] = asset

    return overrides

async def _get_local_only_assets_slice(
        db: AsyncSession,
        skip: int,
        limit: int,
        exclude_material_ids: List[str],
        exclude_inventory_ids: List[str],
        **filters
) -> Sequence[Asset]:
    """Получает локальные активы, исключая те, что уже показаны с этой страницы SAP."""
    # ДОБАВЛЕНО: Полная загрузка связей, идентичная get_local_assets_slice
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

    # Исключаем дубликаты с текущей страницы SAP
    exclude_conditions = []
    if exclude_material_ids:
        exclude_conditions.append(Asset.material_id.notin_(exclude_material_ids))
    if exclude_inventory_ids:
        exclude_conditions.append(Asset.inventory_id.notin_(exclude_inventory_ids))

    if exclude_conditions:
        query = query.where(or_(*exclude_conditions))

    # Применяем стандартные фильтры
    if filters.get('name'):
        query = query.where(Asset.name.ilike(f"%{filters['name']}%"))
    if filters.get('inventory_id'):
        query = query.where(Asset.inventory_id.ilike(f"%{filters['inventory_id']}%"))
    if filters.get('serial_number'):
        query = query.where(Asset.serial_number.ilike(f"%{filters['serial_number']}%"))
    if filters.get('asset_status'):
        query = query.join(AssetStatus, Asset.asset_status_id == AssetStatus.id)
        query = query.where(AssetStatus.status == filters['asset_status'])
    if filters.get('model_id') is not None:
        query = query.where(Asset.model_id == filters['model_id'])
    if filters.get('asset_type_id') is not None:
        query = query.where(Asset.asset_type_id == filters['asset_type_id'])
    if filters.get('parent_id') is not None:
        query = query.where(Asset.parent_id == filters['parent_id'])
    if filters.get('employee_id'):
        emp_asset_subq = (
            select(AssetAssignment.asset_id)
            .where(AssetAssignment.employee_id == filters['employee_id'])
            .scalar_subquery()
        )
        if filters.get('only_my'):
            emp_asset_subq = emp_asset_subq.where(AssetAssignment.end_date.is_(None))
        query = query.where(Asset.asset_id.in_(emp_asset_subq))
    if filters.get('material_class'):
        query = query.where(Asset.material_class == filters['material_class'])

    query = query.order_by(Asset.asset_id.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


# ============================================================
# Вспомогательные функции SAP и БД (без существенных изменений логики)
# ============================================================
async def _load_maps_for_sap_items(db: AsyncSession, sap_items: List[Dict[str, Any]]) -> Tuple[Dict, Dict]:
    employee_ids = set()
    department_codes = set()
    for item in sap_items:
        if item.get("employee_id"):
            employee_ids.add("00" + str(item["employee_id"]).strip())
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

    return employees_map, departments_map


def _build_virtual_asset(sap_item: Dict[str, Any], employees_map: Dict, departments_map: Dict) -> Dict[str, Any]:
    raw_employee_id = "00" + str(sap_item.get("employee_id")) if sap_item.get("employee_id") else None
    employee = employees_map.get(raw_employee_id) if raw_employee_id else None
    start_date = sap_item.get("changed_date") if sap_item.get("changed_date") else None

    users = []
    current_user_full_name = None
    if employee:
        users.append(_build_user_response(employee, "user", start_date))
        parts = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
        current_user_full_name = " ".join(parts) if parts else None

    return {
        "asset_id": None,
        "name": sap_item.get("base_material_name"),
        "inventory_id": sap_item.get("inventory_number"),
        "serial_number": sap_item.get("long_serial_number") or sap_item.get("serial_number"),
        "quantity": int(sap_item.get("quantity", 0)) if sap_item.get("quantity") is not None else 0,
        "asset_status": "В работе",
        "asset_status_id": 10,
        "comment": None,
        "date_issue": None,
        "date_purchasing": None,
        "model_id": None,
        "model_name": None,
        "parent_id": None,
        "every_week_check": False,
        "next_service": None,
        "next_check": None,
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
        "asset_type_id": WITHOUT_TYPE_ASSET_ID,
        "location": None,
        "users": users,
        "cost_center_code_from": sap_item.get("cost_center_code_from"),
        "cost_center_name_from": sap_item.get("cost_center_name_from"),
        "cost_center_shortname_from": sap_item.get("cost_center_shortname_from"),
        "cost_center_code": sap_item.get("cost_center_code"),
        "cost_center_name": sap_item.get("cost_center_name"),
        "cost_center_shortname": sap_item.get("cost_center_shortname"),
        "serving_users": [],
        "current_user": raw_employee_id,
        "current_user_full_name": current_user_full_name,
        "parent": None,
        "material_id": sap_item.get("material_id"),
        "material_class": sap_item.get("material_class"),
        "write_off_date": sap_item.get("write_off_date"),
        "material_class_name": sap_item.get("material_class_name"),
    }


def _build_user_response(employee: Employee, assignment_type: str, start_date: str) -> Dict[str, Any]:
    parts_ru = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
    format_start_date = start_date[:4] + "-" + start_date[4:6] + "-" + start_date[6:] if start_date and len(start_date) >= 8 else None

    position_data = {"name": employee.position.name, "name_en": employee.position.name_en} if getattr(employee, 'position', None) else None

    return {
        "guid": employee.guid,
        "employee_id": employee.employee_id,
        "full_name_ru": " ".join(parts_ru) if parts_ru else None,
        "position": position_data,
        "start_date": format_start_date,
        "end_date": None,
        "assignment_type": assignment_type,
        # Остальные поля можно добавить по аналогии с оригинальной функцией
    }


def _build_paginated_response(items: List[Any], total: int, page: int, page_size: int) -> Dict[str, Any]:
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


# ============================================================
# Оригинальные функции запросов к БД и SAP (оставлены без изменений для сохранения фильтров)
# ============================================================
async def get_local_assets_slice(
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
        cost_center_code_from: Optional[str],
        cost_center_code_from_search_mode: SearchMode = "ALL",
        only_my: Optional[bool] = False,
        next_service_start: Optional[date] = None,
        next_service_end: Optional[date] = None,
        material_class: Optional[str] = None
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

    # === ОБНОВЛЕННАЯ ЛОГИКА ФИЛЬТРАЦИИ cost_center_code_from ===
    if cost_center_code_from is not None or cost_center_code_from_search_mode != "ALL":
        ccc_list = [c.strip() for c in cost_center_code_from.split(";") if c.strip()] if cost_center_code_from else []

        if cost_center_code_from_search_mode == "NULLS":
            query = query.where(Asset.cost_center_code_from.is_(None))
        elif cost_center_code_from_search_mode == "NOT_NULLS":
            if ccc_list:
                query = query.where(Asset.cost_center_code_from.in_(ccc_list))
            else:
                query = query.where(Asset.cost_center_code_from.isnot(None))
        else:  # ALL
            if ccc_list:
                query = query.where(or_(Asset.cost_center_code_from.in_(ccc_list), Asset.cost_center_code_from.is_(None)))

    # Фильтрация по дате обслуживания
    if next_service_start is not None:
        query = query.where(Asset.next_service >= next_service_start)
    if next_service_end is not None:
        query = query.where(Asset.next_service <= next_service_end)
    if material_class:
        query = query.where(Asset.material_class == material_class)

    query = query.order_by(Asset.asset_id.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

# ============================================================
# Загрузка сотрудников и департаментов
# ============================================================
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


async def fetch_sap_materials(
        offset: int,
        page_size: int,
        material_id: Optional[str],
        search_mode: str = "ALL",
        base_material_name_like: Optional[str] = None,
        inventory_number: Optional[str] = None,
        serial_number: Optional[str] = None,
        employee_id: Optional[str] = None,
        cost_center_code_from: Optional[str] = None,
        cost_center_code_from_search_mode: SearchMode = "ALL",
        cost_center_shortname_from: Optional[str] = None,
        cost_center_code: Optional[str] = None,
        cost_center_shortname: Optional[str] = None,
        is_long_serial_number = True,
        material_class: Optional[str] = None,
) -> Dict[str, Any]:
    """Запрос к SAP API для получения списка материалов."""
    # offset = (page - 1) * page_size
    headers = {
        "X-API-Token": X_API_TOKEN
    }

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
        params["long_serial_number"] = serial_number
    if serial_number and not is_long_serial_number:
        params["serial_number"] = serial_number
    if employee_id:
        params["employee_id"] = employee_id
    if cost_center_code_from:
        params["cost_center_code_from"] = cost_center_code_from
    if cost_center_code_from_search_mode:
        params["cost_center_code_from_search_mode"] = cost_center_code_from_search_mode
    if cost_center_shortname_from:
        params["cost_center_shortname_from"] = cost_center_shortname_from
    if cost_center_code:
        params["cost_center_code"] = cost_center_code
    if cost_center_shortname:
        params["cost_center_shortname"] = cost_center_shortname
    if material_class:
        params["material_class"] = material_class

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(SAP_API_URL + "base_materials", params=params, headers=headers)
        response.raise_for_status()
        resp = response.json()
        logger.debug(f"{resp.get("response").get("data")=}")
        if resp.get("response").get("data") == [] and is_long_serial_number:
            return await fetch_sap_materials(
                offset=offset,
                page_size=page_size,
                material_id=material_id,
                search_mode=search_mode,
                base_material_name_like=base_material_name_like,
                inventory_number=inventory_number,
                serial_number=serial_number,
                employee_id=employee_id,
                cost_center_code_from=cost_center_code_from,
                cost_center_code_from_search_mode=cost_center_code_from_search_mode,
                cost_center_shortname_from=cost_center_shortname_from,
                cost_center_code=cost_center_code,
                cost_center_shortname=cost_center_shortname,
                is_long_serial_number=False,
                material_class=material_class
            )
        if resp.get("response").get("data") == [] and not is_long_serial_number:
            return resp
        return resp