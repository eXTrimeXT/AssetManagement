import logging
import requests
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.service.auth.auth_service import require_authorized_user
from app.service.permissions.permissions_rules import FilteredByAccessWithParams, has_write_permission, has_read_permission

from app.schemas.assets.AssetCreate import AssetCreate, AssetCreateRequest
from app.schemas.assets.AssetUpdate import AssetUpdate
from app.schemas.assets.AssetResponse import AssetResponse, AssetShortResponse
from app.schemas.asset_position.AssetPosition import AssetPositionResponse

from app.database.connection import get_db
from app.database.crud_assets import (
    create_asset, get_assets_list, get_asset_by_id, update_asset,
    deactivate_asset, activate_asset, hard_delete_asset,
    get_all_asset_children_recursive, check_duplicate_inventory_id,
    check_duplicate_serial_number, check_parent_exists, get_asset_with_deleted, search_assets_by_name,
    create_asset_for_mu
)
from app.database.crud_catalog import get_asset_model_by_id, search_asset_models_by_name
from app.database.crud_vendors import get_or_create_vendor_by_supplier_number
from app.database import crud_assets
from app.database.crud_asset_types import get_asset_type_by_name_or_en_name
from app.database.crud_software import search_software_by_office_type
from app.database.crud_vendors import search_vendors_by_name
from app.database.crud_warehouses import search_warehouses_by_name

logger = logging.getLogger(__name__)

router_assets = APIRouter(prefix="/assets", tags=["Assets"], dependencies=[Depends(require_authorized_user)])


@router_assets.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset_endpoint(
        asset_in: AssetCreate,
        current_user = Depends(require_authorized_user),
        db: AsyncSession = Depends(get_db)
):
    # 1. Получаем модель с загруженными связями
    model = await get_asset_model_by_id(db, asset_in.model_id)
    if not model:
        logger.warning("Модель актива не найдена")
        raise HTTPException(status_code=400, detail="Модель актива не найдена")

    # 2. Извлекаем en_name типа актива через цепочку: model -> class -> type
    asset_type_en_name = None
    if model.asset_class and model.asset_class.asset_type:
        asset_type_en_name = model.asset_class.asset_type.en_name

    # 3. Проверка write на тип актива (используем en_name, а не ID!)
    if asset_type_en_name and not has_write_permission(current_user, asset_type_en_name):
        logger.error(f"Нет доступа на запись к типу '{asset_type_en_name}'")
        raise HTTPException(403, f"Нет доступа на запись к типу '{asset_type_en_name}'")

    # 4. Остальные проверки
    if await check_duplicate_inventory_id(db, asset_in.inventory_id):
        logger.warning(f"Инвентарный номер уже существует")
        raise HTTPException(status_code=400, detail="Инвентарный номер уже существует")
    if await check_duplicate_serial_number(db, asset_in.serial_number):
        logger.warning(f"Серийный номер уже существует")
        raise HTTPException(status_code=400, detail="Серийный номер уже существует")
    if asset_in.parent_id and not await check_parent_exists(db, asset_in.parent_id):
        logger.warning(f"Родительский актив не найден")
        raise HTTPException(status_code=400, detail="Родительский актив не найден")

    # Добавить проверку по пользователям !!! Иначе error 500

    # 5. Создаём актив
    created_asset = await create_asset(db, asset_in, current_user_id=current_user.user_id)

    # 6. Перезагружаем актив с полными связями для корректной сериализации
    return await get_asset_by_id(db, created_asset.asset_id)


@router_assets.post("/mu/", response_model=AssetResponse)
async def create_asset_for_mu_endpoint(
        asset_data: AssetCreateRequest,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    """Создание нового актива"""

    # Поиск model_id по model_name, заглушка id=1 если не найден
    model_id = 1
    if asset_data.model_name:
        models = await search_asset_models_by_name(db, asset_data.model_name)
        if models:
            model_id = models[0].model_id

    # Поиск type_asset_id по type_asset_en_name, заглушка id=1 если не найден
    type_asset_id = 1
    if asset_data.type_asset_en_name:
        type_asset = await get_asset_type_by_name_or_en_name(db, search_name=asset_data.type_asset_en_name)
        if type_asset:
            type_asset_id = type_asset.asset_type_id

    # Поиск warehouse_id по warehouse_name, заглушка id=1 если не найден
    warehouse_id = 1
    if asset_data.warehouse_name:
        warehouses = await search_warehouses_by_name(db, asset_data.warehouse_name)
        if warehouses:
            warehouse_id = warehouses[0].warehouse_id

    # Поиск parent_id по parent_name, None если не найден
    parent_id = None
    if asset_data.parent_name:
        parents = await search_assets_by_name(db, asset_data.parent_name)
        if parents:
            parent_id = parents[0].asset_id

    # Поиск software_id по software_office_type, None если не найден
    software_id = None
    if asset_data.software_office_type:
        softwares = await search_software_by_office_type(db, asset_data.software_office_type)
        if softwares:
            software_id = softwares[0].id

    # Поиск manufacturer_id по manufacturer_name, None если не найден
    manufacturer_id = None
    if asset_data.manufacturer_name:
        manufacturers = await search_vendors_by_name(db, asset_data.manufacturer_name)
        if manufacturers:
            manufacturer_id = manufacturers[0].vendor_id

    # Поиск vendor_id по vendor_name, None если не найден
    vendor_id = None
    if asset_data.vendor_name:
        vendors = await search_vendors_by_name(db, asset_data.vendor_name)
        if vendors:
            vendor_id = vendors[0].vendor_id

    # Создание актива через create_asset_for_mu
    asset = await create_asset_for_mu(
        db=db,
        name=asset_data.name,
        inventory_id=asset_data.inventory_id,
        serial_number=asset_data.serial_number,
        asset_status=asset_data.asset_status or "Приемка",
        comment=asset_data.comment,
        model_id=model_id,
        type_asset_id=type_asset_id,
        warehouse_id=warehouse_id,
        parent_id=parent_id,
        software_id=software_id,
        manufacturer_id=manufacturer_id,
        vendor_id=vendor_id
    )

    return asset

@router_assets.get("/search", response_model=List[AssetShortResponse])
async def search_assets_endpoint(
        name: str = Query(..., min_length=1),
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    """Поиск активов по name"""
    items = await search_assets_by_name(db, name)

    # Фильтрация по правам доступа
    items_permissions = []
    for item in items:
        try:
            if item.model and item.model.asset_class and item.model.asset_class.asset_type:
                if has_read_permission(current_user, item.model.asset_class.asset_type.en_name):
                    items_permissions.append(item)
        except Exception:
            continue

    return items_permissions

@router_assets.get("/get-from-sap")
async def get_assets_from_sap(
        limit: Optional[int] = Query(None, description="Количество записей"),
        offset: Optional[int] = Query(None, description="Смещение"),
        order: Optional[int] = Query(None, description="Порядок сортировки"),
        inventory_number: Optional[str] = Query(None, description="Фильтр по инвентарному номеру"),
        cost_center_code: Optional[str] = Query(None, description="Фильтр по коду центра затрат"),
        cost_center_code_from: Optional[str] = Query(None, description="Фильтр по коду центра затрат от"),
        base_material_name_like: Optional[str] = Query(None, description="Фильтр по названию базового материала"),
        current_user = Depends(require_authorized_user)
):
    """
    Получает данные материалов из SAP API и возвращает их без сохранения в БД.
    """
    sap_api_url = "http://10.168.143.7:8123/sap/base_materials"
    params = {
        "limit": limit,
        "offset": offset,
        "order": order,
        "inventory_number": inventory_number,
        "cost_center_code": cost_center_code,
        "cost_center_code_from": cost_center_code_from,
        "base_material_name_like": base_material_name_like
    }
    params = {k: v for k, v in params.items() if v is not None}

    try:
        response = requests.get(sap_api_url, params=params)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.error(f"Ошибка при запросе к SAP API: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при запросе к SAP API: {str(e)}")

    if not data.get("success"):
        logger.error(f"SAP API вернул ошибку: {data.get('message')}")
        raise HTTPException(status_code=500, detail=f"SAP API вернул ошибку: {data.get('message')}")

    sap_response = data.get("response", {})
    materials = sap_response.get("data", [])

    return {
        "message": "Данные получены из SAP",
        "total": sap_response.get("total", 0),  # общее количество записей в источнике
        "count": len(materials),                # количество записей в текущем ответе
        "data": materials
    }


@router_assets.post("/add", status_code=status.HTTP_201_CREATED)
async def add_assets_from_sap(
        limit: Optional[int] = Query(None, description="Количество записей"),
        offset: Optional[int] = Query(None, description="Смещение"),
        order: Optional[int] = Query(None, description="Порядок сортировки"),
        inventory_number: Optional[str] = Query(None, description="Фильтр по инвентарному номеру"),
        cost_center_code: Optional[str] = Query(None, description="Фильтр по коду центра затрат"),
        cost_center_code_from: Optional[str] = Query(None, description="Фильтр по коду центра затрат от"),
        base_material_name_like: Optional[str] = Query(None, description="Фильтр по названию базового материала"),
        current_user = Depends(require_authorized_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Получает данные материалов из SAP API и добавляет их в таблицу assets.
    """
    sap_api_url = "http://10.168.143.7:8123/sap/base_materials"
    params = {
        "limit": limit,
        "offset": offset,
        "order": order,
        "inventory_number": inventory_number,
        "cost_center_code": cost_center_code,
        "cost_center_code_from": cost_center_code_from,
        "base_material_name_like": base_material_name_like
    }
    # Удаляем None значения из параметров
    params = {k: v for k, v in params.items() if v is not None}

    try:
        response = requests.get(sap_api_url, params=params)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.error(f"Ошибка при запросе к SAP API: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при запросе к SAP API: {str(e)}")

    if not data.get("success"):
        logger.error(f"SAP API вернул ошибку: {data.get('message')}")
        raise HTTPException(status_code=500, detail=f"SAP API вернул ошибку: {data.get('message')}")

    materials = data.get("response", {}).get("data", [])
    created_count = 0
    skipped_count = 0

    for material in materials:
        inventory_number_val = material.get("inventory_number", "")
        serial_number = material.get("serial_number", "")
        base_material_name = material.get("base_material_name", "")
        supplier_number = material.get("supplier_number", "")

        if not inventory_number_val or not base_material_name:
            skipped_count += 1
            continue

        if await check_duplicate_inventory_id(db, inventory_number_val):
            logger.info(f"Инвентарный номер {inventory_number_val} уже существует, пропускаем")
            skipped_count += 1
            continue

        if serial_number and await check_duplicate_serial_number(db, serial_number):
            logger.info(f"Серийный номер {serial_number} уже существует, пропускаем")
            skipped_count += 1
            continue

        # === Логика работы с vendor_id ===
        asset_kwargs = {
            "inventory_id": inventory_number_val,
            "serial_number": serial_number if serial_number else None,
            "name": base_material_name
        }

        if supplier_number:  # Если supplier_number есть — ищем/создаем вендора
            vendor_id = await get_or_create_vendor_by_supplier_number(db, supplier_number, current_user.user_id)
            asset_kwargs["vendor_id"] = vendor_id
        # Если supplier_number == "" — просто не добавляем vendor_id в kwargs
        # =================================

        asset_in = AssetCreate(**asset_kwargs)

        await create_asset(db, asset_in, current_user_id=current_user.user_id)
        created_count += 1

    return {
        "message": "Импорт завершен",
        "created": created_count,
        "skipped": skipped_count,
        "total_received": len(materials)
    }


@router_assets.get("/", response_model=List[AssetShortResponse])
async def get_assets_endpoint(
        items = Depends(FilteredByAccessWithParams(
            get_assets_list,
            "model.asset_class.asset_type.en_name",
            "read"
        ))
):
    return items


@router_assets.get("/{asset_id}", response_model=AssetResponse)
async def get_asset_endpoint(asset_id: int, db: AsyncSession = Depends(get_db), current_user = Depends(require_authorized_user)):
    asset = await get_asset_by_id(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Актив не найден")

    try:
        if asset.model or asset.model.asset_class or asset.model.asset_class.asset_type:
            if not has_read_permission(current_user, asset.model.asset_class.asset_type.en_name):
                logger.warning(f"Нет доступа для чтения")
                raise HTTPException(status_code=403, detail="Нет доступа для чтения")
    except:
        logger.warning("model_id = NULL")
    return asset


@router_assets.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset_endpoint(
        asset_id: int,
        asset_data: AssetUpdate,
        current_user=Depends(require_authorized_user),
        db: AsyncSession = Depends(get_db)
):
    asset = await get_asset_by_id(db, asset_id)
    if not asset:
        logger.warning(f"Актив не найден")
        raise HTTPException(status_code=404, detail="Актив не найден")

    if not has_write_permission(current_user, asset.model.asset_class.asset_type.en_name):
        logger.warning(f"Нет доступа для записи")
        raise HTTPException(403, "Нет доступа для записи")

    updated_asset = await update_asset(db, asset_id, asset_data, current_user.user_id)
    if not updated_asset:
        logger.error(f"Ошибка при обновлении")
        raise HTTPException(status_code=404, detail="Ошибка при обновлении")
    return updated_asset


@router_assets.post("/{asset_id}/deactivate", response_model=AssetResponse)
async def deactivate_asset_endpoint(
        asset_id: int,
        current_user = Depends(require_authorized_user),
        db: AsyncSession = Depends(get_db)
):
    asset = await get_asset_by_id(db, asset_id)
    if not asset:
        logger.warning(f"Актив не найден")
        raise HTTPException(404, detail="Актив не найден")
    if not has_write_permission(current_user, asset.model.asset_class.asset_type.en_name):
        logger.warning(f"Нет доступа для записи")
        raise HTTPException(403, "Нет доступа для записи")
    return await deactivate_asset(db, asset_id, current_user.user_id)


@router_assets.post("/{asset_id}/activate", response_model=AssetResponse)
async def activate_asset_endpoint(
        asset_id: int,
        current_user = Depends(require_authorized_user),
        db: AsyncSession = Depends(get_db)
):
    activated = await activate_asset(db, asset_id, current_user.user_id)
    if not activated:
        logger.warning(f"Актив не найден")
        raise HTTPException(status_code=404, detail="Актив не найден")

    if not has_write_permission(current_user, activated.model.asset_class.asset_type.en_name):
        logger.warning(f"Нет доступа для записи")
        raise HTTPException(403, "Нет доступа для записи")
    return activated


@router_assets.delete("/{asset_id}/hard", status_code=status.HTTP_204_NO_CONTENT)
async def hard_delete_asset_endpoint(
        asset_id: int,
        current_user = Depends(require_authorized_user),
        db: AsyncSession = Depends(get_db)
):
    asset = await get_asset_with_deleted(db, asset_id)

    if not asset:
        logger.warning(f"Актив не найден")
        raise HTTPException(status_code=404, detail="Актив не найден")

    if asset.deleted_at is None:
        logger.warning(f"Сначала деактивируйте актив.")
        raise HTTPException(status_code=400, detail="Сначала деактивируйте актив.")

    if not has_write_permission(current_user, asset.model.asset_class.asset_type.en_name):
        logger.warning(f"Нет доступа для записи")
        raise HTTPException(403, "Нет доступа для записи")

    success = await hard_delete_asset(db, asset_id, current_user.user_id)
    if not success:
        logger.error(f"Ошибка при удалении актива")
        raise HTTPException(status_code=500, detail="Ошибка при удалении актива")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router_assets.get("/{asset_id}/children", response_model=List[AssetShortResponse])
async def get_all_asset_children_endpoint(
        asset_id: int,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user),
        max_depth: Optional[int] = Query(None, ge=1, le=10)
):
    """
    Получить всех дочерних активов рекурсивно.
    Возвращает только те, на которые у пользователя есть право `read`.
    """
    parent = await get_asset_with_deleted(db, asset_id)
    if not parent:
        logger.warning(f"Родительский актив не найден")
        raise HTTPException(status_code=404, detail="Родительский актив не найден")

    if not has_read_permission(current_user, parent.model.asset_class.asset_type.en_name):
        logger.warning(f"Нет доступа для чтения")
        raise HTTPException(status_code=403, detail="Нет доступа для чтения")

    # Получаем детей с загруженными связями
    children = await get_all_asset_children_recursive(db, asset_id, max_depth)

    # === ФИЛЬТРАЦИЯ ПО ПРАВАМ ===
    filtered_children = [
        child for child in children
        if (
                child.model
                and child.model.asset_class
                and child.model.asset_class.asset_type
                and has_read_permission(current_user, child.model.asset_class.asset_type.en_name)
        )
    ]

    # Конвертируем в ответ (Pydantic v2)
    return [AssetShortResponse.model_validate(child) for child in filtered_children]



# === НОВЫЕ ЭНДПОИНТЫ ДЛЯ КАРТЫ АКТИВОВ ===
@router_assets.get("/{asset_id}/positions", response_model=List[AssetPositionResponse])
async def get_asset_positions(
        asset_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    Получение всех позиций актива на картах (история + текущая).
    """
    # Проверяем существование актива
    asset = await crud_assets.get_active_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    positions = await crud_assets.get_asset_positions(db, asset_id)
    return positions


@router_assets.get("/{asset_id}/position/active", response_model=AssetPositionResponse)
async def get_active_asset_position(
        asset_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    Получение текущей (активной) позиции актива.
    """
    # Проверяем существование актива
    asset = await crud_assets.get_active_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    position = await crud_assets.get_active_asset_position(db, asset_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    return position