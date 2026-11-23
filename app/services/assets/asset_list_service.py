import logging
import os
from datetime import date, datetime
from typing import List, Dict, Optional, Any, Sequence, Tuple, Literal

from sqlalchemy import select, inspect, Integer, or_, cast
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
IsSapMode = Literal["ALL", "LOCAL", "SAP"]

# Максимальное количество SAP-активов, которое мы готовы загрузить за один раз
# (защита от OOM; при необходимости увеличьте или сделайте батчевую загрузку)
SAP_MAX_FETCH = 5000
SAP_FETCH_BATCH = 500


# ==============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ==============================================================================
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
        is_sap: str = "ALL",
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
    """
    Возвращает объединённый список активов из локальной БД и SAP с корректной
    пагинацией и истинным total.

    Логика:
    Загружаем локальные активы (все, без пагинации) по локальным фильтрам.
    Загружаем SAP-активы по SAP-фильтрам.
    Для каждого SAP-актива ищем локальное переопределение (по material_id/inventory_id)
       и сливаем данные (SAP-база + локальные поля).
    Чисто локальные активы (без material_id, не переопределения) добавляем как есть.
    Применяем локальные фильтры к объединённому списку (asset_type_id, model_id,
       asset_status, parent_id, next_service, material_class, cost_center_*).
    Сортируем и пагинируем.
    total = len(отфильтрованного объединённого списка).
    """

    # ------------------------------------------------------------------
    # Загружаем ВСЕ локальные активы по локальным фильтрам (без пагинации)
    # ------------------------------------------------------------------
    is_sap = is_sap.lower()
    local_assets: List[Asset] = []

    if is_sap == "ALL" or is_sap == "LOCAL":
        local_assets = await _load_all_local_assets(
            db=db,
            asset_id=asset_id,
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
            material_class=material_class,
        )

    # Строим карты переопределений: material_id -> Asset, inventory_id -> Asset
    overrides_by_material: Dict[str, Asset] = {}
    overrides_by_inventory: Dict[str, Asset] = {}
    local_only_assets: List[Asset] = []  # без material_id (чисто локальные)

    for asset in local_assets:
        if asset.material_id:
            overrides_by_material[asset.material_id] = asset
        if asset.inventory_id:
            overrides_by_inventory[asset.inventory_id] = asset
        if not asset.material_id:
            local_only_assets.append(asset)

    # ------------------------------------------------------------------
    # Загружаем SAP-активы (только если не задан asset_id — это локальный поиск)
    # ------------------------------------------------------------------
    sap_items: List[Dict[str, Any]] = []
    sap_total_from_api = 0

    # При поиске по конкретному asset_id (локальный ID) SAP не нужен
    # Если стоит параметр is_sap = 'ALL', 'SAP - тогда показываем активы из SAP
    # При поиске по material_id — наоборот, нужен только SAP (локальные переопределения
    # подтянутся по material_id).
    should_fetch_sap = asset_id is None

    logger.debug(f"{is_sap=}")

    if is_sap == "ALL" or is_sap == "SAP":
        if should_fetch_sap:
            sap_items, sap_total_from_api = await _fetch_all_sap_materials(
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
                material_class=material_class,
            )

    # ------------------------------------------------------------------
    # Собираем объединённый список
    # ------------------------------------------------------------------
    combined: List[Dict[str, Any]] = []
    used_local_asset_ids: set = set()  # чтобы не добавить чисто локальный дважды

    # 3a. SAP-активы (с подмешиванием локальных переопределений)
    # Загружаем связанные сущности для переопределений и SAP-employee одним заходом
    override_asset_ids = [a.asset_id for a in overrides_by_material.values()]
    override_asset_ids += [a.asset_id for a in overrides_by_inventory.values() if a.asset_id not in override_asset_ids]
    overrides_full = await _load_local_assets_by_ids(db, override_asset_ids)

    # Перезаполняем карты полноценными объектами (с eager-loaded связями)
    overrides_by_material.clear()
    overrides_by_inventory.clear()
    for asset in overrides_full:
        if asset.material_id:
            overrides_by_material[asset.material_id] = asset
        if asset.inventory_id:
            overrides_by_inventory[asset.inventory_id] = asset
        # used_local_asset_ids.add(asset.asset_id)

    # Обогащение SAP-элементов сотрудниками/департаментами
    employees_map, departments_map = await _load_maps_for_sap_items(db, sap_items)

    for sap_item in sap_items:
        mat = sap_item.get("material_id")
        inv = sap_item.get("inventory_number")
        override = overrides_by_material.get(mat) if mat else None
        if override is None and inv:
            override = overrides_by_inventory.get(inv)

        if override is not None:
            merged = _merge_sap_with_local(sap_item, override, employees_map, departments_map)
            used_local_asset_ids.add(override.asset_id)
        else:
            merged = _build_virtual_asset(sap_item, employees_map, departments_map)

        combined.append(merged)

    # 3b. Чисто локальные активы (без material_id и не использованные как переопределения)
    for asset in local_only_assets:
        if asset.asset_id in used_local_asset_ids:
            continue
        combined.append(_asset_to_response_dict(asset))
        used_local_asset_ids.add(asset.asset_id)

    # 3c. Локальные активы с material_id, которые НЕ совпали ни с одним SAP-элементом
    # (SAP мог отфильтровать их по своим фильтрам) — добавляем как локальные,
    # чтобы они не потерялись. Но ТОЛЬКО если SAP вернул непустой результат,
    # иначе это может быть просто актив, отсутствующий в SAP.
    # Согласно требованию "SAP-активы + локальные активы = смешанные активы + фильтры",
    # такие активы должны попасть в выдачу, если проходят локальные фильтры.
    for asset in local_assets:
        if asset.asset_id in used_local_asset_ids:
            continue
        # Актив с material_id, но SAP его не вернул (или SAP не запрашивался)
        combined.append(_asset_to_response_dict(asset))
        used_local_asset_ids.add(asset.asset_id)

    # ------------------------------------------------------------------
    # Применяем ЛОКАЛЬНЫЕ фильтры к объединённому списку
    #    (asset_type_id, model_id, asset_status, parent_id, next_service, material_class,
    #     cost_center_* — т.к. после слияния у SAP-активов появились локальные поля)
    # ------------------------------------------------------------------
    combined = _filter_combined(
        combined,
        asset_status=asset_status,
        model_id=model_id,
        asset_type_id=asset_type_id,
        parent_id=parent_id,
        next_service_start=next_service_start,
        next_service_end=next_service_end,
        material_class=material_class,
        cost_center_code=cost_center_code,
        cost_center_code_from=cost_center_code_from,
        cost_center_shortname=cost_center_shortname,
        cost_center_shortname_from=cost_center_shortname_from,
        cost_center_code_from_search_mode=cost_center_code_from_search_mode,
        cost_center_shortname_from_mode=cost_center_shortname_from_mode,
        cost_center_shortname_mode=cost_center_shortname_mode,
    )

    # ------------------------------------------------------------------
    # Сортировка и пагинация
    # ------------------------------------------------------------------
    combined.sort(key=_sort_key, reverse=True)

    total = len(combined)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = combined[start:end]

    return _build_paginated_response(page_items, total=total, page=page, page_size=page_size)


# ==============================================================================
# ЗАГРУЗКА ЛОКАЛЬНЫХ АКТИВОВ
# ==============================================================================
def _local_assets_base_query():
    return select(Asset).options(
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


def _apply_local_filters(
        query,
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
        cost_center_code_from_search_mode: SearchMode = "ALL",
        cost_center_code: Optional[str] = None,
        cost_center_shortname: Optional[str] = None,
        cost_center_shortname_from: Optional[str] = None,
        cost_center_shortname_from_mode: SearchMode = "ALL",
        cost_center_shortname_mode: SearchMode = "ALL",
        next_service_start: Optional[date] = None,
        next_service_end: Optional[date] = None,
        material_class: Optional[str] = None,
):
    """Применяет локальные SQL-фильтры к запросу Asset."""
    if asset_id is not None:
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
    if material_class:
        query = query.where(Asset.material_class == material_class)

    if asset_status:
        query = query.join(AssetStatus, Asset.asset_status_id == AssetStatus.id)
        query = query.where(AssetStatus.status == asset_status)

    if employee_id:
        emp_subq = (
            select(AssetAssignment.asset_id)
            .where(AssetAssignment.employee_id == employee_id)
        )
        if only_my:
            emp_subq = emp_subq.where(AssetAssignment.end_date.is_(None))
        query = query.where(Asset.asset_id.in_(emp_subq.scalar_subquery()))

    # cost_center_code (владелец)
    if cost_center_code:
        ccc_list = [c.strip() for c in cost_center_code.split(";") if c.strip()]
        if ccc_list:
            query = query.where(Asset.cost_center_code.in_(ccc_list))

    # cost_center_code_from (ответственный) с режимом
    if cost_center_code_from is not None or cost_center_code_from_search_mode != "ALL":
        ccc_from_list = [c.strip() for c in cost_center_code_from.split(";") if c.strip()] if cost_center_code_from else []
        if cost_center_code_from_search_mode == "NULLS":
            query = query.where(Asset.cost_center_code_from.is_(None))
        elif cost_center_code_from_search_mode == "NOT_NULLS":
            if ccc_from_list:
                query = query.where(Asset.cost_center_code_from.in_(ccc_from_list))
            else:
                query = query.where(Asset.cost_center_code_from.isnot(None))
        elif ccc_from_list:
            query = query.where(or_(
                Asset.cost_center_code_from.in_(ccc_from_list),
                Asset.cost_center_code_from.is_(None),
            ))

    # cost_center_shortname (владелец) с режимом
    if cost_center_shortname is not None or cost_center_shortname_mode != "ALL":
        ccs_list = [c.strip() for c in cost_center_shortname.split(";") if c.strip()] if cost_center_shortname else []
        if cost_center_shortname_mode == "NULLS":
            query = query.where(Asset.cost_center_shortname.is_(None))
        elif cost_center_shortname_mode == "NOT_NULLS":
            if ccs_list:
                query = query.where(Asset.cost_center_shortname.in_(ccs_list))
            else:
                query = query.where(Asset.cost_center_shortname.isnot(None))
        elif ccs_list:
            query = query.where(or_(
                Asset.cost_center_shortname.in_(ccs_list),
                Asset.cost_center_shortname.is_(None),
            ))

    # cost_center_shortname_from (ответственный) с режимом
    if cost_center_shortname_from is not None or cost_center_shortname_from_mode != "ALL":
        ccs_from_list = [c.strip() for c in cost_center_shortname_from.split(";") if c.strip()] if cost_center_shortname_from else []
        if cost_center_shortname_from_mode == "NULLS":
            query = query.where(Asset.cost_center_shortname_from.is_(None))
        elif cost_center_shortname_from_mode == "NOT_NULLS":
            if ccs_from_list:
                query = query.where(Asset.cost_center_shortname_from.in_(ccs_from_list))
            else:
                query = query.where(Asset.cost_center_shortname_from.isnot(None))
        elif ccs_from_list:
            query = query.where(or_(
                Asset.cost_center_shortname_from.in_(ccs_from_list),
                Asset.cost_center_shortname_from.is_(None),
            ))

    if next_service_start is not None:
        query = query.where(Asset.next_service >= next_service_start)
    if next_service_end is not None:
        query = query.where(Asset.next_service <= next_service_end)

    return query


async def _load_all_local_assets(
        db: AsyncSession,
        **filters,
) -> List[Asset]:
    """Загружает ВСЕ локальные активы по фильтрам (без пагинации)."""
    query = _local_assets_base_query()
    query = _apply_local_filters(query, **filters)
    query = query.order_by(Asset.asset_id.desc())
    result = await db.execute(query)
    return list(result.scalars().unique().all())


async def _load_local_assets_by_ids(db: AsyncSession, asset_ids: List[int]) -> List[Asset]:
    """Загружает локальные активы по списку asset_id с eager-loaded связями."""
    if not asset_ids:
        return []
    query = _local_assets_base_query().where(Asset.asset_id.in_(asset_ids))
    result = await db.execute(query)
    return list(result.scalars().unique().all())


# ==============================================================================
# ЗАГРУЗКА SAP
# ==============================================================================
async def _fetch_all_sap_materials(
        material_id: Optional[str] = None,
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
        material_class: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Загружает SAP-активы батчами до SAP_MAX_FETCH или до полного покрытия total.
    Возвращает (список_элементов, total_из_api).
    """
    all_items: List[Dict[str, Any]] = []
    offset = 0
    total_from_api = 0

    while offset < SAP_MAX_FETCH:
        resp = await fetch_sap_materials(
            offset=offset,
            page_size=SAP_FETCH_BATCH,
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
            material_class=material_class,
        )

        if not resp.get("success"):
            logger.error("SAP API вернул success=false: %s", resp)
            break

        response_data = resp.get("response", {}) or {}
        batch = response_data.get("data") or []
        total_from_api = response_data.get("total", total_from_api) or total_from_api

        if not batch:
            break

        all_items.extend(batch)
        offset += len(batch)

        # Если сервер вернул меньше, чем размер батча — данные закончились
        if len(batch) < SAP_FETCH_BATCH:
            break
        # Если уже покрыли total — тоже стоп
        if total_from_api and offset >= total_from_api:
            break

    return all_items, total_from_api


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
    """Один запрос к SAP API с fallback по серийному номеру."""
    headers = {"X-API-Token": X_API_TOKEN}
    params: Dict[str, Any] = {
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
        if is_long_serial_number:
            params["long_serial_number"] = serial_number
        else:
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

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                SAP_API_URL + "base_materials", params=params, headers=headers
            )
            response.raise_for_status()
            resp = response.json()
            logger.debug(
                "SAP response: data_len=%s, total=%s",
                len(resp.get("response", {}).get("data", []) or []),
                resp.get("response", {}).get("total"),
            )
    except httpx.HTTPError as e:
        logger.error("Ошибка запроса к SAP: %s", e)
        return {"success": False, "response": {"data": [], "total": 0}}

    # Fallback: если пусто по long_serial_number — пробуем short
    if (
            resp.get("response", {}).get("data") == []
            and serial_number
            and is_long_serial_number
    ):
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
            material_class=material_class,
        )

    return resp


# ==============================================================================
# СЛИЯНИЕ SAP + LOCAL
# ==============================================================================
def _merge_sap_with_local(
        sap_item: Dict[str, Any],
        local_asset: Asset,
        employees_map: Dict[str, Any],
        departments_map: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Строит объединённый dict: база из SAP + локальные поля.
    Локальные поля имеют приоритет (переопределяют SAP).
    """
    merged = _build_virtual_asset(sap_item, employees_map, departments_map)

    # Локальные скалярные поля (переопределяют SAP)
    if local_asset.name:
        merged['name'] = local_asset.name
    if local_asset.serial_number:
        merged['serial_number'] = local_asset.serial_number
    if local_asset.comment is not None:
        merged['comment'] = local_asset.comment
    if local_asset.date_issue is not None:
        merged['date_issue'] = local_asset.date_issue.isoformat() if hasattr(local_asset.date_issue, 'isoformat') else local_asset.date_issue
    if local_asset.date_purchasing is not None:
        merged['date_purchasing'] = local_asset.date_purchasing.isoformat() if hasattr(local_asset.date_purchasing, 'isoformat') else local_asset.date_purchasing
    if local_asset.model_id is not None:
        merged['model_id'] = local_asset.model_id
    if local_asset.model_name:
        merged['model_name'] = local_asset.model_name
    if local_asset.asset_type_id is not None:
        merged['asset_type_id'] = local_asset.asset_type_id
    if local_asset.asset_type:
        merged['asset_type_name'] = local_asset.asset_type.name
    if local_asset.parent_id is not None:
        merged['parent_id'] = local_asset.parent_id
    if local_asset.asset_status_id is not None:
        merged['asset_status_id'] = local_asset.asset_status_id
    if local_asset.asset_status:
        merged['asset_status'] = local_asset.asset_status.status
    if local_asset.parent_name:
        merged['parent_name'] = local_asset.parent_name
    if local_asset.manufacturer_name:
        merged['manufacturer_name'] = local_asset.manufacturer_name
    if local_asset.vendor_name:
        merged['vendor_name'] = local_asset.vendor_name
    if local_asset.os_name:
        merged['os_name'] = local_asset.os_name

    # Локальные MVZ-поля (переопределяют SAP, если не None)
    for field in (
            'cost_center_code', 'cost_center_name', 'cost_center_shortname',
            'cost_center_code_from', 'cost_center_name_from', 'cost_center_shortname_from',
            'material_class',
    ):
        local_val = getattr(local_asset, field, None)
        if local_val is not None:
            merged[field] = local_val

    merged['asset_id'] = local_asset.asset_id
    merged['inventory_id'] = local_asset.inventory_id or merged.get('inventory_id')
    merged['material_id'] = local_asset.material_id or merged.get('material_id')

    if local_asset.created_by:
        merged['created_by'] = local_asset.created_by
    if local_asset.updated_by:
        merged['updated_by'] = local_asset.updated_by
    if local_asset.created_at:
        merged['created_at'] = local_asset.created_at.isoformat()
    if local_asset.updated_at:
        merged['updated_at'] = local_asset.updated_at.isoformat()

    # next_service / next_check / периоды — берём из локального, если задано
    if local_asset.next_service is not None:
        merged['next_service'] = local_asset.next_service.isoformat() if hasattr(local_asset.next_service, 'isoformat') else local_asset.next_service
    if getattr(local_asset, 'next_check', None) is not None:
        nc = local_asset.next_check
        merged['next_check'] = nc.isoformat() if hasattr(nc, 'isoformat') else nc
    if getattr(local_asset, 'service_period', None) is not None:
        merged['service_period'] = local_asset.service_period
    if getattr(local_asset, 'check_period', None) is not None:
        merged['check_period'] = local_asset.check_period
    if getattr(local_asset, 'every_week_check', None) is not None:
        merged['every_week_check'] = local_asset.every_week_check

    # Локация
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

    # Пользователи — локальные имеют приоритет (заменяют SAP employee)
    if local_asset.assignments:
        active_assignments = [a for a in local_asset.assignments if a.end_date is None]
        if active_assignments:
            users_list = []
            for a in active_assignments:
                emp = a.employee
                if emp:
                    users_list.append(_employee_to_user_dict(
                        emp,
                        assignment_type=a.assignment_type.value if hasattr(a.assignment_type, 'value') else str(a.assignment_type),
                        start_date=a.start_date.isoformat() if a.start_date else None,
                    ))
            merged['users'] = users_list
            first_emp = active_assignments[0].employee
            if first_emp:
                merged['current_user'] = first_emp.employee_id
                parts = [p for p in [first_emp.last_name, first_emp.first_name, first_emp.middle_name] if p]
                merged['current_user_full_name'] = " ".join(parts) if parts else None

    return merged


def _asset_to_response_dict(asset: Asset) -> Dict[str, Any]:
    """Преобразует локальный Asset в dict формата ответа (для чисто локальных активов)."""
    data = AssetResponse.model_validate(asset, from_attributes=True).model_dump()
    # Гарантируем наличие material_id / inventory_id
    data.setdefault("material_id", asset.material_id)
    data.setdefault("inventory_id", asset.inventory_id)
    return data


def _sort_key(item: Dict[str, Any]) -> Tuple[int, int, str]:
    """
    Ключ сортировки: сначала локальные (asset_id > 0) по убыванию asset_id,
    потом SAP-виртуальные (asset_id = None) по material_id.
    При reverse=True получаем: локальные новые сверху, затем SAP.
    """
    asset_id = item.get("asset_id")
    material_id = item.get("material_id") or ""
    if asset_id is not None:
        return (1, asset_id, "")
    return (0, 0, str(material_id))


# ==============================================================================
# ФИЛЬТРАЦИЯ ОБЪЕДИНЁННОГО СПИСКА
# ==============================================================================
def _filter_combined(
        items: List[Dict[str, Any]],
        asset_status: Optional[str] = None,
        model_id: Optional[int] = None,
        asset_type_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        next_service_start: Optional[date] = None,
        next_service_end: Optional[date] = None,
        material_class: Optional[str] = None,
        cost_center_code: Optional[str] = None,
        cost_center_code_from: Optional[str] = None,
        cost_center_shortname: Optional[str] = None,
        cost_center_shortname_from: Optional[str] = None,
        cost_center_code_from_search_mode: SearchMode = "ALL",
        cost_center_shortname_from_mode: SearchMode = "ALL",
        cost_center_shortname_mode: SearchMode = "ALL",
) -> List[Dict[str, Any]]:
    """
    Применяет локальные фильтры к объединённому списку dict-ов.
    Работает поверх слияния: у SAP-активов после merge уже есть локальные поля.
    """
    # Парсим списки MVZ
    ccc_list = [c.strip() for c in cost_center_code.split(";") if c.strip()] if cost_center_code else []
    ccc_from_list = [c.strip() for c in cost_center_code_from.split(";") if c.strip()] if cost_center_code_from else []
    ccs_list = [c.strip() for c in cost_center_shortname.split(";") if c.strip()] if cost_center_shortname else []
    ccs_from_list = [c.strip() for c in cost_center_shortname_from.split(";") if c.strip()] if cost_center_shortname_from else []

    def _norm_date(v) -> Optional[date]:
        if v is None:
            return None
        if isinstance(v, date):
            return v
        s = str(v)
        # ISO
        try:
            return date.fromisoformat(s[:10])
        except Exception:
            pass
        # DD-MM-YYYY
        try:
            return datetime.strptime(s[:10], "%d-%m-%Y").date()
        except Exception:
            return None

    result: List[Dict[str, Any]] = []
    for item in items:
        # asset_status
        if asset_status is not None:
            if item.get("asset_status") != asset_status:
                continue
        # model_id
        if model_id is not None:
            if item.get("model_id") != model_id:
                continue
        # asset_type_id
        if asset_type_id is not None:
            if item.get("asset_type_id") != asset_type_id:
                continue
        # parent_id
        if parent_id is not None:
            if item.get("parent_id") != parent_id:
                continue
        # material_class
        if material_class is not None:
            if item.get("material_class") != material_class:
                continue

        # next_service
        ns = _norm_date(item.get("next_service"))
        if next_service_start is not None:
            if ns is None or ns < next_service_start:
                continue
        if next_service_end is not None:
            if ns is None or ns > next_service_end:
                continue

        # cost_center_code (владелец) — точное совпадение с одним из значений
        if ccc_list:
            if item.get("cost_center_code") not in ccc_list:
                continue

        # cost_center_code_from с режимом
        item_ccc_from = item.get("cost_center_code_from")
        if cost_center_code_from_search_mode == "NULLS":
            if item_ccc_from is not None:
                continue
        elif cost_center_code_from_search_mode == "NOT_NULLS":
            if item_ccc_from is None:
                continue
            if ccc_from_list and item_ccc_from not in ccc_from_list:
                continue
        elif ccc_from_list:
            if item_ccc_from is not None and item_ccc_from not in ccc_from_list:
                continue

        # cost_center_shortname с режимом
        item_ccs = item.get("cost_center_shortname")
        if cost_center_shortname_mode == "NULLS":
            if item_ccs is not None:
                continue
        elif cost_center_shortname_mode == "NOT_NULLS":
            if item_ccs is None:
                continue
            if ccs_list and item_ccs not in ccs_list:
                continue
        elif ccs_list:
            if item_ccs is not None and item_ccs not in ccs_list:
                continue

        # cost_center_shortname_from с режимом
        item_ccs_from = item.get("cost_center_shortname_from")
        if cost_center_shortname_from_mode == "NULLS":
            if item_ccs_from is not None:
                continue
        elif cost_center_shortname_from_mode == "NOT_NULLS":
            if item_ccs_from is None:
                continue
            if ccs_from_list and item_ccs_from not in ccs_from_list:
                continue
        elif ccs_from_list:
            if item_ccs_from is not None and item_ccs_from not in ccs_from_list:
                continue

        result.append(item)
    return result


# ==============================================================================
# ОБОГАЩЕНИЕ SAP-ЭЛЕМЕНТОВ
# ==============================================================================
async def _load_maps_for_sap_items(
        db: AsyncSession, sap_items: List[Dict[str, Any]]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    employee_ids = set()
    department_codes = set()
    for item in sap_items:
        if item.get("employee_id"):
            raw = str(item["employee_id"]).strip()
            # SAP может возвращать 8-значный табельный; приводим к "00..."
            emp_id = raw if raw.startswith("00") else "00" + raw
            employee_ids.add(emp_id)
        if item.get("department_code"):
            department_codes.add(item["department_code"])

    employees_map: Dict[str, Any] = {}
    if employee_ids:
        employees = await _get_employees_by_ids(db, list(employee_ids))
        employees_map = {emp.employee_id: emp for emp in employees}

    departments_map: Dict[str, Any] = {}
    if department_codes:
        departments = await _get_departments_by_codes(db, list(department_codes))
        departments_map = {dept.short_name: dept for dept in departments}

    return employees_map, departments_map


def _build_virtual_asset(
        sap_item: Dict[str, Any],
        employees_map: Dict[str, Any],
        departments_map: Dict[str, Any],
) -> Dict[str, Any]:
    """Строит виртуальный актив из данных SAP."""
    raw_employee_id = None
    if sap_item.get("employee_id"):
        raw = str(sap_item["employee_id"]).strip()
        raw_employee_id = raw if raw.startswith("00") else "00" + raw

    employee = employees_map.get(raw_employee_id) if raw_employee_id else None
    start_date = sap_item.get("changed_date") or None

    users = []
    current_user_full_name = None
    if employee:
        users.append(_employee_to_user_dict(employee, "user", start_date))
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


def _employee_to_user_dict(employee: Any, assignment_type: str, start_date: Any) -> Dict[str, Any]:
    """
    Безопасно (без ленивых загрузок) собирает dict пользователя из ORM-объекта Employee.
    """
    emp_dict = getattr(employee, '__dict__', {})

    def safe_get(key, default=None):
        val = emp_dict.get(key, default)
        if val is not None and hasattr(val, 'isoformat'):
            return val.isoformat()
        return val

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

    parts_ru = [p for p in [safe_get('last_name'), safe_get('first_name'), safe_get('middle_name')] if p]
    parts_en = [p for p in [safe_get('last_name_en'), safe_get('first_name_en'), safe_get('middle_name_en')] if p]

    position_data = None
    pos = safe_get('position')
    if pos:
        pos_dict = getattr(pos, '__dict__', {})
        position_data = {"name": pos_dict.get('name'), "name_en": pos_dict.get('name_en')}

    # Нормализуем start_date
    if start_date is not None and hasattr(start_date, 'isoformat'):
        start_date = start_date.isoformat()
    elif start_date is not None and isinstance(start_date, str) and len(start_date) >= 8 and start_date[4] != '-':
        # SAP отдаёт YYYYMMDD
        s = str(start_date)
        start_date = f"{s[:4]}-{s[4:6]}-{s[6:8]}"

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
        "start_date": start_date,
        "end_date": None,
        "assignment_type": assignment_type,
    }


# ==============================================================================
# ЗАГРУЗКА СОТРУДНИКОВ / ДЕПАРТАМЕНТОВ
# ==============================================================================
async def _get_employees_by_ids(db: AsyncSession, employee_ids: List[str]) -> Sequence[Any]:
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


async def _get_departments_by_codes(db: AsyncSession, department_codes: List[str]) -> Sequence[Any]:
    if not department_codes:
        return []
    query = select(ZupDepartment).where(ZupDepartment.short_name.in_(department_codes))
    result = await db.execute(query)
    return result.scalars().all()


# ==============================================================================
# ПАГИНАЦИЯ
# ==============================================================================
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