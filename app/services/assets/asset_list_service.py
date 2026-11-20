import logging
import os
from datetime import date
from typing import List, Dict, Optional, Any, Sequence, Tuple, Literal
from sqlalchemy import select, inspect, Integer, or_, cast, and_, func
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
#         cost_center_shortname_from: Optional[str] = None,
#         cost_center_shortname_from_mode: SearchMode = "ALL",
#         cost_center_code_from: Optional[str] = None,
#         cost_center_code_from_search_mode: SearchMode = "ALL",
#         cost_center_shortname: Optional[str] = None,
#         cost_center_shortname_mode: SearchMode = "ALL",
#         cost_center_code: Optional[str] = None,
#         next_service_start: Optional[date] = None,
#         next_service_end: Optional[date] = None,
#         material_class: Optional[str] = None,
# ) -> Dict[str, Any]:
#     # 1. Оптимизация: прямой поиск по локальному asset_id
#     if asset_id is not None:
#         local_orm_items = await get_local_assets_slice(
#             db=db, skip=0, limit=1, asset_id=asset_id, material_id=material_id,
#             name=name, inventory_id=inventory_id, serial_number=serial_number,
#             asset_status=asset_status, model_id=model_id, asset_type_id=asset_type_id,
#             parent_id=parent_id, employee_id=employee_id, only_my=only_my,
#             cost_center_code_from=cost_center_code_from,
#             cost_center_code_from_search_mode=cost_center_code_from_search_mode,
#             next_service_start=next_service_start, next_service_end=next_service_end,
#             material_class=material_class
#         )
#         if local_orm_items:
#             return _build_paginated_response(
#                 [AssetResponse.model_validate(item, from_attributes=True).model_dump() for item in local_orm_items],
#                 total=1, page=1, page_size=1
#             )
#         return _build_paginated_response([], total=0, page=1, page_size=1)
#
#     # 2. Считаем количество локальных активов, подходящих под фильтры (включая only_my)
#     local_total = await _get_local_assets_count(
#         db=db,
#         material_id=material_id,
#         name=name,
#         inventory_id=inventory_id,
#         serial_number=serial_number,
#         asset_status=asset_status,
#         model_id=model_id,
#         asset_type_id=asset_type_id,
#         parent_id=parent_id,
#         employee_id=employee_id,
#         only_my=only_my,
#         cost_center_code_from=cost_center_code_from,
#         cost_center_code_from_search_mode=cost_center_code_from_search_mode,
#         cost_center_code=cost_center_code,
#         cost_center_shortname=cost_center_shortname,
#         cost_center_shortname_from=cost_center_shortname_from,
#         cost_center_shortname_from_mode=cost_center_shortname_from_mode,
#         cost_center_shortname_mode=cost_center_shortname_mode,
#         next_service_start=next_service_start,
#         next_service_end=next_service_end,
#         material_class=material_class
#     )
#
#     result_items = []
#     sap_total = 0
#
#     # 3. Забираем локальные активы для текущей страницы (они имеют абсолютный приоритет)
#     skip_local = (page - 1) * page_size
#     if skip_local < local_total:
#         local_orm_items = await get_local_assets_slice(
#             db=db, skip=skip_local, limit=page_size,
#             name=name, inventory_id=inventory_id, serial_number=serial_number,
#             asset_status=asset_status, model_id=model_id, asset_type_id=asset_type_id,
#             parent_id=parent_id, employee_id=employee_id, only_my=only_my,
#             cost_center_code_from=cost_center_code_from,
#             cost_center_code_from_search_mode=cost_center_code_from_search_mode,
#             cost_center_code=cost_center_code, cost_center_shortname=cost_center_shortname,
#             cost_center_shortname_from=cost_center_shortname_from,
#             next_service_start=next_service_start, next_service_end=next_service_end,
#             material_class=material_class
#         )
#         result_items = [AssetResponse.model_validate(item, from_attributes=True).model_dump() for item in local_orm_items]
#
#     # 4. Если страница не заполнена локальными записями, добираем недостающее из SAP
#     remaining_slots = page_size - len(result_items)
#
#     if remaining_slots > 0:
#         # Вычисляем смещение для SAP, чтобы пагинация работала бесшовно после исчерпания локальных записей
#         sap_offset = max(0, skip_local - local_total)
#         sap_limit = remaining_slots * 2  # Берем с запасом на случай фильтрации дубликатов
#
#         sap_response = await fetch_sap_materials(
#             offset=sap_offset,
#             page_size=sap_limit,
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
#         if sap_response.get("success") and "data" in sap_response.get("response", {}):
#             sap_items_raw = sap_response["response"]["data"]
#             sap_total = sap_response["response"].get("total", 0)
#
#             # Собираем идентификаторы уже добавленных локальных активов для исключения дубликатов
#             existing_inv_ids = {item.get("inventory_id") for item in result_items if item.get("inventory_id")}
#             existing_mat_ids = {item.get("material_id") for item in result_items if item.get("material_id")}
#
#             filtered_sap = []
#             for item in sap_items_raw:
#                 inv = item.get("inventory_number")
#                 mat = item.get("material_id")
#
#                 # Пропускаем, если такой актив уже есть в локальной выдаче
#                 if (inv and inv in existing_inv_ids) or (mat and mat in existing_mat_ids):
#                     continue
#
#                 filtered_sap.append(item)
#
#             # Обогащаем отфильтрованные SAP-активы данными сотрудников и департаментов
#             if filtered_sap:
#                 employees_map, departments_map = await _load_maps_for_sap_items(db, filtered_sap)
#                 for item in filtered_sap:
#                     if len(result_items) >= page_size:
#                         break  # Страница заполнена, прекращаем добавление
#                     result_items.append(_build_virtual_asset(item, employees_map, departments_map))
#
#     # КОРРЕКЦИЯ TOTAL:
#     # Активы с material_id считаются переопределениями SAP-активов и уже учтены в sap_total.
#     # Поэтому к sap_total мы прибавляем только количество чисто локальных активов (у которых material_id IS NULL).
#
#     local_only_count_query = select(func.count(Asset.asset_id)).select_from(Asset)
#
#     # Применяем все те же фильтры, что и для обычного подсчета
#     if name: local_only_count_query = local_only_count_query.where(Asset.name.ilike(f"%{name}%"))
#     if inventory_id: local_only_count_query = local_only_count_query.where(Asset.inventory_id.ilike(f"%{inventory_id}%"))
#     if serial_number: local_only_count_query = local_only_count_query.where(Asset.serial_number.ilike(f"%{serial_number}%"))
#     if model_id is not None: local_only_count_query = local_only_count_query.where(Asset.model_id == model_id)
#     if asset_type_id is not None: local_only_count_query = local_only_count_query.where(Asset.asset_type_id == asset_type_id)
#     if parent_id is not None: local_only_count_query = local_only_count_query.where(Asset.parent_id == parent_id)
#     if material_class: local_only_count_query = local_only_count_query.where(Asset.material_class == material_class)
#
#     if asset_status:
#         local_only_count_query = local_only_count_query.join(AssetStatus, Asset.asset_status_id == AssetStatus.id).where(AssetStatus.status == asset_status)
#
#     if employee_id:
#         emp_subq = select(AssetAssignment.asset_id).where(AssetAssignment.employee_id == employee_id)
#         if only_my: emp_subq = emp_subq.where(AssetAssignment.end_date.is_(None))
#         local_only_count_query = local_only_count_query.where(Asset.asset_id.in_(emp_subq.scalar_subquery()))
#
#     if cost_center_code:
#         ccc_list = [c.strip() for c in cost_center_code.split(";") if c.strip()]
#         if ccc_list: local_only_count_query = local_only_count_query.where(Asset.cost_center_code.in_(ccc_list))
#
#     if cost_center_code_from is not None or cost_center_code_from_search_mode != "ALL":
#         ccc_from_list = [c.strip() for c in cost_center_code_from.split(";") if c.strip()] if cost_center_code_from else []
#         if cost_center_code_from_search_mode == "NULLS":
#             local_only_count_query = local_only_count_query.where(Asset.cost_center_code_from.is_(None))
#         elif cost_center_code_from_search_mode == "NOT_NULLS":
#             local_only_count_query = local_only_count_query.where(Asset.cost_center_code_from.in_(ccc_from_list) if ccc_from_list else Asset.cost_center_code_from.isnot(None))
#         elif ccc_from_list:
#             local_only_count_query = local_only_count_query.where(or_(Asset.cost_center_code_from.in_(ccc_from_list), Asset.cost_center_code_from.is_(None)))
#
#     if cost_center_shortname:
#         ccs_list = [c.strip() for c in cost_center_shortname.split(";") if c.strip()]
#         if ccs_list: local_only_count_query = local_only_count_query.where(Asset.cost_center_shortname.in_(ccs_list))
#
#     if cost_center_shortname_from is not None or cost_center_shortname_from_mode != "ALL":
#         ccs_from_list = [c.strip() for c in cost_center_shortname_from.split(";") if c.strip()] if cost_center_shortname_from else []
#         if cost_center_shortname_from_mode == "NULLS":
#             local_only_count_query = local_only_count_query.where(Asset.cost_center_shortname_from.is_(None))
#         elif cost_center_shortname_from_mode == "NOT_NULLS":
#             local_only_count_query = local_only_count_query.where(Asset.cost_center_shortname_from.in_(ccs_from_list) if ccs_from_list else Asset.cost_center_shortname_from.isnot(None))
#         elif ccs_from_list:
#             local_only_count_query = local_only_count_query.where(or_(Asset.cost_center_shortname_from.in_(ccs_from_list), Asset.cost_center_shortname_from.is_(None)))
#
#     if next_service_start: local_only_count_query = local_only_count_query.where(Asset.next_service >= next_service_start)
#     if next_service_end: local_only_count_query = local_only_count_query.where(Asset.next_service <= next_service_end)
#
#     # === КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ===
#     # Считаем только те локальные активы, у которых НЕТ material_id.
#     # Активы с material_id уже учтены в sap_total как переопределения SAP-активов.
#     local_only_count_query = local_only_count_query.where(Asset.material_id.is_(None))
#
#     local_only_count = (await db.execute(local_only_count_query)).scalar_one()
#
#     # Итоговый total = SAP активы + Чисто локальные активы (без material_id)
#     final_total = sap_total + local_only_count
#
#     return _build_paginated_response(result_items, total=final_total, page=page, page_size=page_size)


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
    # 1. Оптимизация: прямой поиск по локальному asset_id
    if asset_id is not None:
        local_orm_items = await get_local_assets_slice(
            db=db, skip=0, limit=1, asset_id=asset_id, material_id=material_id,
            name=name, inventory_id=inventory_id, serial_number=serial_number,
            asset_status=asset_status, model_id=model_id, asset_type_id=asset_type_id,
            parent_id=parent_id, employee_id=employee_id, only_my=only_my,
            cost_center_code_from=cost_center_code_from,
            cost_center_code_from_search_mode=cost_center_code_from_search_mode,
            next_service_start=next_service_start, next_service_end=next_service_end,
            material_class=material_class
        )
        if local_orm_items:
            return _build_paginated_response(
                [AssetResponse.model_validate(item, from_attributes=True).model_dump() for item in local_orm_items],
                total=1, page=1, page_size=1
            )
        return _build_paginated_response([], total=0, page=1, page_size=1)

    # 2. Считаем количество локальных активов, подходящих под фильтры
    local_total = await _get_local_assets_count(
        db=db,
        material_id=material_id,
        name=name,
        inventory_id=inventory_id,
        serial_number=serial_number,
        asset_status=asset_status,
        model_id=model_id,
        asset_type_id=asset_type_id,
        parent_id=parent_id,
        employee_id=employee_id,
        only_my=only_my,
        cost_center_code_from=cost_center_code_from,
        cost_center_code_from_search_mode=cost_center_code_from_search_mode,
        cost_center_code=cost_center_code,
        cost_center_shortname=cost_center_shortname,
        cost_center_shortname_from=cost_center_shortname_from,
        cost_center_shortname_from_mode=cost_center_shortname_from_mode,
        cost_center_shortname_mode=cost_center_shortname_mode,
        next_service_start=next_service_start,
        next_service_end=next_service_end,
        material_class=material_class
    )

    result_items = []
    sap_total = 0

    # 3. Забираем локальные активы для текущей страницы (они имеют абсолютный приоритет)
    skip_local = (page - 1) * page_size
    if skip_local < local_total:
        local_orm_items = await get_local_assets_slice(
            db=db, skip=skip_local, limit=page_size,
            name=name, inventory_id=inventory_id, serial_number=serial_number,
            asset_status=asset_status, model_id=model_id, asset_type_id=asset_type_id,
            parent_id=parent_id, employee_id=employee_id, only_my=only_my,
            cost_center_code_from=cost_center_code_from,
            cost_center_code_from_search_mode=cost_center_code_from_search_mode,
            cost_center_code=cost_center_code, cost_center_shortname=cost_center_shortname,
            cost_center_shortname_from=cost_center_shortname_from,
            next_service_start=next_service_start, next_service_end=next_service_end,
            material_class=material_class
        )
        result_items = [AssetResponse.model_validate(item, from_attributes=True).model_dump() for item in local_orm_items]

    # 4. Если страница не заполнена локальными записями, добираем недостающее из SAP
    remaining_slots = page_size - len(result_items)

    if remaining_slots > 0:
        sap_offset = max(0, skip_local - local_total)
        sap_limit = remaining_slots * 2  # Берем с запасом на случай фильтрации дубликатов

        sap_response = await fetch_sap_materials(
            offset=sap_offset,
            page_size=sap_limit,
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

            existing_inv_ids = {item.get("inventory_id") for item in result_items if item.get("inventory_id")}
            existing_mat_ids = {item.get("material_id") for item in result_items if item.get("material_id")}

            filtered_sap = []
            for item in sap_items_raw:
                inv = item.get("inventory_number")
                mat = item.get("material_id")

                # Пропускаем, если такой актив уже есть в локальной выдаче
                if (inv and inv in existing_inv_ids) or (mat and mat in existing_mat_ids):
                    continue

                filtered_sap.append(item)

            # Обогащаем отфильтрованные SAP-активы данными сотрудников и департаментов
            if filtered_sap:
                employees_map, departments_map = await _load_maps_for_sap_items(db, filtered_sap)
                for item in filtered_sap:
                    if len(result_items) >= page_size:
                        break  # Страница заполнена, прекращаем добавление
                    result_items.append(_build_virtual_asset(item, employees_map, departments_map))

    # ==============================================================================
    # 5. ДОБОР: Если страница всё ещё не заполнена, добираем чисто локальными активами
    # ==============================================================================
    remaining_slots_after_sap = page_size - len(result_items)
    if remaining_slots_after_sap > 0:
        # Исключаем те, что уже есть в result_items, чтобы гарантировать отсутствие дублей
        exclude_material_ids = [item.get("material_id") for item in result_items if item.get("material_id")]
        exclude_inventory_ids = [item.get("inventory_id") for item in result_items if item.get("inventory_id")]
        exclude_asset_ids = [item.get("asset_id") for item in result_items if item.get("asset_id")]

        local_fillers = await _get_local_only_assets_slice(
            db=db,
            skip=0,
            limit=remaining_slots_after_sap,
            exclude_material_ids=exclude_material_ids,
            exclude_inventory_ids=exclude_inventory_ids,
            exclude_asset_ids=exclude_asset_ids,
            name=name,
            inventory_id=inventory_id,
            serial_number=serial_number,
            asset_status=asset_status,
            model_id=model_id,
            asset_type_id=asset_type_id,
            parent_id=parent_id,
            employee_id=employee_id,
            only_my=only_my,
            cost_center_code_from=cost_center_code_from,
            cost_center_code=cost_center_code,
            cost_center_shortname=cost_center_shortname,
            cost_center_shortname_from=cost_center_shortname_from,
            next_service_start=next_service_start,
            next_service_end=next_service_end,
            material_class=material_class
        )

        # Добавляем их в общий список
        result_items.extend([AssetResponse.model_validate(item, from_attributes=True).model_dump() for item in local_fillers])

    # 6. КОРРЕКЦИЯ TOTAL
    local_only_count_query = select(func.count(Asset.asset_id)).select_from(Asset)

    if name: local_only_count_query = local_only_count_query.where(Asset.name.ilike(f"%{name}%"))
    if inventory_id: local_only_count_query = local_only_count_query.where(Asset.inventory_id.ilike(f"%{inventory_id}%"))
    if serial_number: local_only_count_query = local_only_count_query.where(Asset.serial_number.ilike(f"%{serial_number}%"))
    if model_id is not None: local_only_count_query = local_only_count_query.where(Asset.model_id == model_id)
    if asset_type_id is not None: local_only_count_query = local_only_count_query.where(Asset.asset_type_id == asset_type_id)
    if parent_id is not None: local_only_count_query = local_only_count_query.where(Asset.parent_id == parent_id)
    if material_class: local_only_count_query = local_only_count_query.where(Asset.material_class == material_class)

    if asset_status:
        local_only_count_query = local_only_count_query.join(AssetStatus, Asset.asset_status_id == AssetStatus.id).where(AssetStatus.status == asset_status)

    if employee_id:
        emp_subq = select(AssetAssignment.asset_id).where(AssetAssignment.employee_id == employee_id)
        if only_my: emp_subq = emp_subq.where(AssetAssignment.end_date.is_(None))
        local_only_count_query = local_only_count_query.where(Asset.asset_id.in_(emp_subq.scalar_subquery()))

    if cost_center_code:
        ccc_list = [c.strip() for c in cost_center_code.split(";") if c.strip()]
        if ccc_list: local_only_count_query = local_only_count_query.where(Asset.cost_center_code.in_(ccc_list))

    if cost_center_code_from is not None or cost_center_code_from_search_mode != "ALL":
        ccc_from_list = [c.strip() for c in cost_center_code_from.split(";") if c.strip()] if cost_center_code_from else []
        if cost_center_code_from_search_mode == "NULLS":
            local_only_count_query = local_only_count_query.where(Asset.cost_center_code_from.is_(None))
        elif cost_center_code_from_search_mode == "NOT_NULLS":
            local_only_count_query = local_only_count_query.where(Asset.cost_center_code_from.in_(ccc_from_list) if ccc_from_list else Asset.cost_center_code_from.isnot(None))
        elif ccc_from_list:
            local_only_count_query = local_only_count_query.where(or_(Asset.cost_center_code_from.in_(ccc_from_list), Asset.cost_center_code_from.is_(None)))

    if cost_center_shortname:
        ccs_list = [c.strip() for c in cost_center_shortname.split(";") if c.strip()]
        if ccs_list: local_only_count_query = local_only_count_query.where(Asset.cost_center_shortname.in_(ccs_list))

    if cost_center_shortname_from is not None or cost_center_shortname_from_mode != "ALL":
        ccs_from_list = [c.strip() for c in cost_center_shortname_from.split(";") if c.strip()] if cost_center_shortname_from else []
        if cost_center_shortname_from_mode == "NULLS":
            local_only_count_query = local_only_count_query.where(Asset.cost_center_shortname_from.is_(None))
        elif cost_center_shortname_from_mode == "NOT_NULLS":
            local_only_count_query = local_only_count_query.where(Asset.cost_center_shortname_from.in_(ccs_from_list) if ccs_from_list else Asset.cost_center_shortname_from.isnot(None))
        elif ccs_from_list:
            local_only_count_query = local_only_count_query.where(or_(Asset.cost_center_shortname_from.in_(ccs_from_list), Asset.cost_center_shortname_from.is_(None)))

    if next_service_start: local_only_count_query = local_only_count_query.where(Asset.next_service >= next_service_start)
    if next_service_end: local_only_count_query = local_only_count_query.where(Asset.next_service <= next_service_end)

    # === КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ===
    # Считаем только те локальные активы, у которых НЕТ material_id.
    # Активы с material_id уже учтены в sap_total как переопределения SAP-активов.
    local_only_count_query = local_only_count_query.where(Asset.material_id.is_(None))

    local_only_count = (await db.execute(local_only_count_query)).scalar_one()

    # Итоговый total = SAP активы + Чисто локальные активы (без material_id)
    final_total = sap_total + local_only_count

    return _build_paginated_response(result_items, total=final_total, page=page, page_size=page_size)

async def get_local_assets_slice(
        db: AsyncSession,
        skip: int,
        limit: int,
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
        cost_center_code_from: Optional[str] = None,
        cost_center_code_from_search_mode: SearchMode = "ALL",
        only_my: Optional[bool] = False,
        next_service_start: Optional[date] = None,
        next_service_end: Optional[date] = None,
        material_class: Optional[str] = None,
        cost_center_code: Optional[str] = None,
        cost_center_shortname: Optional[str] = None,
        cost_center_shortname_from: Optional[str] = None,
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

    # === ЛОГИКА ФИЛЬТРАЦИИ cost_center_code_from ===
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

    # Дополнительные фильтры MVZ (для совместимости с вызовами из get_assets_list_with_sap)
    if cost_center_code:
        ccc_list = [c.strip() for c in cost_center_code.split(";") if c.strip()]
        if ccc_list:
            query = query.where(Asset.cost_center_code.in_(ccc_list))
    if cost_center_shortname:
        ccs_list = [c.strip() for c in cost_center_shortname.split(";") if c.strip()]
        if ccs_list:
            query = query.where(Asset.cost_center_shortname.in_(ccs_list))
    if cost_center_shortname_from:
        ccs_from_list = [c.strip() for c in cost_center_shortname_from.split(";") if c.strip()]
        if ccs_from_list:
            query = query.where(or_(Asset.cost_center_shortname_from.in_(ccs_from_list), Asset.cost_center_shortname_from.is_(None)))

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

# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (Четко разделены по задачам)
# ==============================================================================
def _filter_items_by_local_params(
        items: List[Dict[str, Any]],
        asset_status: Optional[str] = None,
        asset_type_id: Optional[int] = None,
        model_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        next_service_start: Optional[date] = None,
        next_service_end: Optional[date] = None,
        material_class: Optional[str] = None,
        cost_center_code: Optional[str] = None,
        cost_center_code_from: Optional[str] = None,
        cost_center_shortname: Optional[str] = None,
        cost_center_shortname_from: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Фильтрует список словарей по параметрам, которые SAP API не поддерживает."""
    filtered = []

    # Предварительно парсим списки MVZ для быстрого поиска
    ccc_list = [c.strip() for c in cost_center_code.split(";") if c.strip()] if cost_center_code else []
    ccc_from_list = [c.strip() for c in cost_center_code_from.split(";") if c.strip()] if cost_center_code_from else []
    ccs_list = [c.strip() for c in cost_center_shortname.split(";") if c.strip()] if cost_center_shortname else []
    ccs_from_list = [c.strip() for c in cost_center_shortname_from.split(";") if c.strip()] if cost_center_shortname_from else []

    for item in items:
        if asset_status is not None and item.get('asset_status') != asset_status:
            continue
        if asset_type_id is not None and item.get('asset_type_id') != asset_type_id:
            continue
        if model_id is not None and item.get('model_id') != model_id:
            continue
        if parent_id is not None and item.get('parent_id') != parent_id:
            continue
        if material_class is not None and item.get('material_class') != material_class:
            continue

        # Даты ТО
        ns = item.get('next_service')
        if next_service_start and ns:
            ns_date = ns if isinstance(ns, date) else (date.fromisoformat(str(ns)) if str(ns) else None)
            if ns_date and ns_date < next_service_start:
                continue
        if next_service_end and ns:
            ns_date = ns if isinstance(ns, date) else (date.fromisoformat(str(ns)) if str(ns) else None)
            if ns_date and ns_date > next_service_end:
                continue

        # MVZ Фильтры
        if ccc_list and item.get('cost_center_code') not in ccc_list:
            continue

        item_ccc_from = item.get('cost_center_code_from')
        if cost_center_code_from:
            if ccc_from_list and item_ccc_from not in ccc_from_list and item_ccc_from is not None:
                continue

        item_ccs = item.get('cost_center_shortname')
        if ccs_list and item_ccs not in ccs_list:
            continue

        item_ccs_from = item.get('cost_center_shortname_from')
        if cost_center_shortname_from:
            if ccs_from_list and item_ccs_from not in ccs_from_list and item_ccs_from is not None:
                continue

        filtered.append(item)
    return filtered

async def _get_local_only_assets_slice(
        db: AsyncSession, skip: int, limit: int,
        exclude_material_ids: List[str],
        exclude_inventory_ids: List[str],
        exclude_asset_ids: List[int],
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
        cost_center_code_from: Optional[str] = None,
        cost_center_code: Optional[str] = None,
        cost_center_shortname: Optional[str] = None,
        cost_center_shortname_from: Optional[str] = None,
        next_service_start: Optional[date] = None,
        next_service_end: Optional[date] = None,
        material_class: Optional[str] = None,
) -> Sequence[Asset]:
    """Получает срез локальных активов, исключая переданные ID и применяя все фильтры."""
    query = select(Asset).options(
        selectinload(Asset.asset_type), selectinload(Asset.asset_status), selectinload(Asset.model),
        selectinload(Asset.parent).options(selectinload(Asset.asset_type), selectinload(Asset.asset_status), selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop)),
        selectinload(Asset.asset_positions).selectinload(AssetPosition.workshop),
        selectinload(Asset.assignments).options(selectinload(AssetAssignment.employee).options(selectinload(Employee.position), selectinload(Employee.group).options(selectinload(ZupDepartment.parent).options(selectinload(ZupDepartment.parent).options(selectinload(ZupDepartment.parent)))))),
    )

    # Исключения
    exclude_conds = []
    if exclude_asset_ids: exclude_conds.append(Asset.asset_id.notin_(exclude_asset_ids))
    if exclude_material_ids: exclude_conds.append(Asset.material_id.notin_(exclude_material_ids))
    if exclude_inventory_ids: exclude_conds.append(Asset.inventory_id.notin_(exclude_inventory_ids))
    if exclude_conds:
        query = query.where(and_(*exclude_conds))

    # Базовые фильтры
    if asset_id: query = query.where(Asset.asset_id == asset_id)
    if material_id: query = query.where(Asset.material_id == material_id)
    if name: query = query.where(Asset.name.ilike(f"%{name}%"))
    if inventory_id: query = query.where(Asset.inventory_id.ilike(f"%{inventory_id}%"))
    if serial_number: query = query.where(Asset.serial_number.ilike(f"%{serial_number}%"))
    if model_id is not None: query = query.where(Asset.model_id == model_id)
    if asset_type_id is not None: query = query.where(Asset.asset_type_id == asset_type_id)
    if parent_id is not None: query = query.where(Asset.parent_id == parent_id)
    if material_class: query = query.where(Asset.material_class == material_class)

    if asset_status:
        query = query.join(AssetStatus, Asset.asset_status_id == AssetStatus.id).where(AssetStatus.status == asset_status)

    if employee_id:
        emp_subq = select(AssetAssignment.asset_id).where(AssetAssignment.employee_id == employee_id)
        if only_my: emp_subq = emp_subq.where(AssetAssignment.end_date.is_(None))
        query = query.where(Asset.asset_id.in_(emp_subq.scalar_subquery()))

    # MVZ Фильтры
    if cost_center_code:
        ccc_list = [c.strip() for c in cost_center_code.split(";") if c.strip()]
        if ccc_list: query = query.where(Asset.cost_center_code.in_(ccc_list))

    if cost_center_code_from:
        ccc_from_list = [c.strip() for c in cost_center_code_from.split(";") if c.strip()] if cost_center_code_from else []
        query = query.where(or_(Asset.cost_center_code_from.in_(ccc_from_list), Asset.cost_center_code_from.is_(None)))

    if cost_center_shortname:
        ccs_list = [c.strip() for c in cost_center_shortname.split(";") if c.strip()]
        if ccs_list: query = query.where(Asset.cost_center_shortname.in_(ccs_list))

    if cost_center_shortname_from:
        ccs_from_list = [c.strip() for c in cost_center_shortname_from.split(";") if c.strip()] if cost_center_shortname_from else []
        query = query.where(or_(Asset.cost_center_shortname_from.in_(ccs_from_list), Asset.cost_center_shortname_from.is_(None)))

    if next_service_start: query = query.where(Asset.next_service >= next_service_start)
    if next_service_end: query = query.where(Asset.next_service <= next_service_end)

    return (await db.execute(query.order_by(Asset.asset_id.desc()).offset(skip).limit(limit))).scalars().all()

async def _get_local_assets_count(
        db: AsyncSession,
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
        cost_center_code_from: Optional[str] = None,
        cost_center_code_from_search_mode: str = "ALL",
        cost_center_code: Optional[str] = None,
        cost_center_shortname: Optional[str] = None,
        cost_center_shortname_from: Optional[str] = None,
        cost_center_shortname_from_mode: str = "ALL",
        cost_center_shortname_mode: str = "ALL",
        next_service_start: Optional[date] = None,
        next_service_end: Optional[date] = None,
        material_class: Optional[str] = None,
) -> int:
    """Считает количество локальных активов по тем же фильтрам, что и _get_local_only_assets_slice."""
    # Мы используем тот же набор условий, но заменяем select(Asset) на select(func.count(Asset.asset_id))
    # Для простоты и избежания дублирования кода, мы можем вызвать _get_local_only_assets_slice с limit=0
    # и извлечь count из скомпилированного запроса, но проще продублировать логику where, так как она короткая.
    # Чтобы не дублировать 50 строк, сделаем хак: получим запрос, заменим колонки на count и выполним.

    # Создаем фиктивный вызов для получения объекта query (без выполнения)
    # Но проще и надежнее просто написать компактный count-запрос:
    query = select(func.count(Asset.asset_id))

    if material_id: query = query.where(Asset.material_id == material_id)
    if name: query = query.where(Asset.name.ilike(f"%{name}%"))
    if inventory_id: query = query.where(Asset.inventory_id.ilike(f"%{inventory_id}%"))
    if serial_number: query = query.where(Asset.serial_number.ilike(f"%{serial_number}%"))
    if model_id is not None: query = query.where(Asset.model_id == model_id)
    if asset_type_id is not None: query = query.where(Asset.asset_type_id == asset_type_id)
    if parent_id is not None: query = query.where(Asset.parent_id == parent_id)
    if material_class: query = query.where(Asset.material_class == material_class)

    if asset_status:
        query = query.join(AssetStatus, Asset.asset_status_id == AssetStatus.id).where(AssetStatus.status == asset_status)

    if employee_id:
        emp_subq = select(AssetAssignment.asset_id).where(AssetAssignment.employee_id == employee_id)
        if only_my: emp_subq = emp_subq.where(AssetAssignment.end_date.is_(None))
        query = query.where(Asset.asset_id.in_(emp_subq.scalar_subquery()))

    if cost_center_code:
        ccc_list = [c.strip() for c in cost_center_code.split(";") if c.strip()]
        if ccc_list: query = query.where(Asset.cost_center_code.in_(ccc_list))

    if cost_center_code_from is not None or cost_center_code_from_search_mode != "ALL":
        ccc_from_list = [c.strip() for c in cost_center_code_from.split(";") if c.strip()] if cost_center_code_from else []
        if cost_center_code_from_search_mode == "NULLS":
            query = query.where(Asset.cost_center_code_from.is_(None))
        elif cost_center_code_from_search_mode == "NOT_NULLS":
            query = query.where(Asset.cost_center_code_from.in_(ccc_from_list) if ccc_from_list else Asset.cost_center_code_from.isnot(None))
        elif ccc_from_list:
            query = query.where(or_(Asset.cost_center_code_from.in_(ccc_from_list), Asset.cost_center_code_from.is_(None)))

    if cost_center_shortname:
        ccs_list = [c.strip() for c in cost_center_shortname.split(";") if c.strip()]
        if ccs_list: query = query.where(Asset.cost_center_shortname.in_(ccs_list))

    if cost_center_shortname_from is not None or cost_center_shortname_from_mode != "ALL":
        ccs_from_list = [c.strip() for c in cost_center_shortname_from.split(";") if c.strip()] if cost_center_shortname_from else []
        if cost_center_shortname_from_mode == "NULLS":
            query = query.where(Asset.cost_center_shortname_from.is_(None))
        elif cost_center_shortname_from_mode == "NOT_NULLS":
            query = query.where(Asset.cost_center_shortname_from.in_(ccs_from_list) if ccs_from_list else Asset.cost_center_shortname_from.isnot(None))
        elif ccs_from_list:
            query = query.where(or_(Asset.cost_center_shortname_from.in_(ccs_from_list), Asset.cost_center_shortname_from.is_(None)))

    if next_service_start: query = query.where(Asset.next_service >= next_service_start)
    if next_service_end: query = query.where(Asset.next_service <= next_service_end)

    return (await db.execute(query)).scalar_one()

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

# =========================================================================
# Функции слияния и обогащения (без изменений логики, только форматирование)
# =========================================================================
async def _get_local_override(db: AsyncSession, material_id: Optional[str], inventory_id: Optional[str]) -> Optional[Asset]:
    conditions = []
    if material_id:
        conditions.append(Asset.material_id == material_id)
    if inventory_id:
        conditions.append(Asset.inventory_id == inventory_id)
    if not conditions:
        return None

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
        is_long_serial_number: bool = True,
        material_class: Optional[str] = None,
) -> Dict[str, Any]:
    headers = {"X-API-Token": X_API_TOKEN}
    params = {
        "limit": page_size,
        "offset": offset,
        "employee_id_search_mode": search_mode,
    }
    if material_id: params["material_id"] = material_id
    if base_material_name_like: params["base_material_name_like"] = base_material_name_like
    if inventory_number: params["inventory_number"] = inventory_number
    if serial_number: params["long_serial_number"] = serial_number
    if serial_number and not is_long_serial_number: params["serial_number"] = serial_number
    if employee_id: params["employee_id"] = employee_id
    if cost_center_code_from: params["cost_center_code_from"] = cost_center_code_from
    if cost_center_code_from_search_mode: params["cost_center_code_from_search_mode"] = cost_center_code_from_search_mode
    if cost_center_shortname_from: params["cost_center_shortname_from"] = cost_center_shortname_from
    if cost_center_code: params["cost_center_code"] = cost_center_code
    if cost_center_shortname: params["cost_center_shortname"] = cost_center_shortname
    if material_class: params["material_class"] = material_class

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(SAP_API_URL + "base_materials", params=params, headers=headers)
        response.raise_for_status()
        resp = response.json()
        logger.debug(f"SAP Response data length: {len(resp.get('response', {}).get('data', []))}")

        if resp.get("response", {}).get("data") == [] and is_long_serial_number:
            return await fetch_sap_materials(
                offset=offset, page_size=page_size, material_id=material_id, search_mode=search_mode,
                base_material_name_like=base_material_name_like, inventory_number=inventory_number,
                serial_number=serial_number, employee_id=employee_id,
                cost_center_code_from=cost_center_code_from,
                cost_center_code_from_search_mode=cost_center_code_from_search_mode,
                cost_center_shortname_from=cost_center_shortname_from,
                cost_center_code=cost_center_code, cost_center_shortname=cost_center_shortname,
                is_long_serial_number=False, material_class=material_class
            )
        return resp

def _merge_sap_with_local(sap_item: Dict[str, Any], local_asset: Asset, db: AsyncSession) -> Dict[str, Any]:
    merged = _build_virtual_asset(sap_item, {}, {})

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

    merged['asset_id'] = local_asset.asset_id
    if local_asset.created_by: merged['created_by'] = local_asset.created_by
    if local_asset.updated_by: merged['updated_by'] = local_asset.updated_by
    if local_asset.created_at: merged['created_at'] = local_asset.created_at.isoformat() if local_asset.created_at else None
    if local_asset.updated_at: merged['updated_at'] = local_asset.updated_at.isoformat() if local_asset.updated_at else None

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
                        "birth_date": emp.birth_date.isoformat() if emp.birth_date else None,
                        "employment_date": emp.employment_date.isoformat() if emp.employment_date else None,
                        "dismissal_date": emp.dismissal_date.isoformat() if emp.dismissal_date else None,
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
            first_emp = active_assignments[0].employee
            if first_emp:
                merged['current_user'] = first_emp.employee_id
                parts = [p for p in [first_emp.last_name, first_emp.first_name, first_emp.middle_name] if p]
                merged['current_user_full_name'] = " ".join(parts) if parts else None

    return merged

async def _get_local_overrides_for_list(db: AsyncSession, sap_items: List[Dict[str, Any]]) -> Dict[str, Asset]:
    material_ids = [item.get("material_id") for item in sap_items if item.get("material_id")]
    inventory_ids = [item.get("inventory_number") for item in sap_items if item.get("inventory_number")]
    if not material_ids and not inventory_ids:
        return {}

    conditions = []
    if material_ids:
        conditions.append(Asset.material_id.in_(material_ids))
    if inventory_ids:
        conditions.append(Asset.inventory_id.in_(inventory_ids))

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

def _build_user_response(employee: Any, assignment_type: str, start_date: str) -> Dict[str, Any]:
    """
    Безопасно извлекает данные из объекта сотрудника, полностью избегая
    триггеров ленивой загрузки SQLAlchemy (MissingGreenlet).
    """
    # Прямой доступ к словарю атрибутов объекта, минуя дескрипторы SQLAlchemy
    emp_dict = getattr(employee, '__dict__', {})

    def safe_get(key, default=None):
        val = emp_dict.get(key, default)
        # Если это дата/время, безопасно преобразуем в строку ISO
        if val is not None and hasattr(val, 'isoformat'):
            return val.isoformat()
        return val

    parts_ru = [p for p in [safe_get('last_name'), safe_get('first_name'), safe_get('middle_name')] if p]
    parts_en = [p for p in [safe_get('last_name_en'), safe_get('first_name_en'), safe_get('middle_name_en')] if p]

    format_start_date = (
        str(start_date)[:4] + "-" + str(start_date)[4:6] + "-" + str(start_date)[6:]
        if start_date and len(str(start_date)) >= 8 else None
    )

    position_data = None
    pos = safe_get('position')
    if pos:
        pos_dict = getattr(pos, '__dict__', {})
        position_data = {
            "name": pos_dict.get('name'),
            "name_en": pos_dict.get('name_en'),
        }

    def _get_dept_dict(dept_obj):
        if not dept_obj:
            return None
        d = getattr(dept_obj, '__dict__', {})
        return {
            "guid": d.get('guid'),
            "name": d.get('name'),
            "name_en": d.get('name_en'),
            "short_name": d.get('short_name'),
            "creation_date": safe_get('creation_date', d.get('creation_date')),
            "closure_date": safe_get('closure_date', d.get('closure_date')),
            "parent_guid": d.get('parent_guid'),
        }

    return {
        "guid": safe_get('guid'),
        "employee_id": safe_get('employee_id'),
        "birth_date": safe_get('birth_date'),
        "employment_date": safe_get('employment_date'),
        "dismissal_date": safe_get('dismissal_date'),
        "phone": safe_get('phone'),
        "email": safe_get('email'),
        "comment": safe_get('comment'),
        "position_guid": safe_get('position_guid'),
        "department_guid": safe_get('department_guid'),
        "created_at": safe_get('created_at'),
        "updated_at": safe_get('updated_at'),
        "full_name_ru": " ".join(parts_ru) if parts_ru else None,
        "full_name_en": " ".join(parts_en) if parts_en else None,
        "society": _get_dept_dict(safe_get('society')),
        "department": _get_dept_dict(safe_get('department')),
        "division": _get_dept_dict(safe_get('division')),
        "group": safe_get('group'),
        "position": position_data,
        "start_date": format_start_date,
        "end_date": None,
        "assignment_type": assignment_type,
    }

async def _get_employees_by_ids(db: AsyncSession, employee_ids: List[str]) -> list[Any] | Sequence[Any]:
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

async def _get_departments_by_codes(db: AsyncSession, department_codes: List[str]) -> list[Any] | Sequence[Any]:
    if not department_codes:
        return []
    query = select(ZupDepartment).where(ZupDepartment.short_name.in_(department_codes))
    result = await db.execute(query)
    return result.scalars().all()
