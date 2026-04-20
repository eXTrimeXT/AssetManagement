from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.database.connection import get_db
from app.schemas.assets.AssetCreate import AssetCreate
from app.schemas.assets.AssetUpdate import AssetUpdate
from app.schemas.assets.AssetResponse import AssetResponse, AssetShortResponse

# Импорт CRUD операций
from app.database.crud_assets import (
    create_asset,
    get_assets_list,
    get_asset_by_id,
    update_asset,
    deactivate_asset,
    activate_asset,
    hard_delete_asset,
    get_all_asset_children_recursive,
    check_duplicate_inventory_id,
    check_duplicate_serial_number,
    check_parent_exists,
)
from app.database.crud_assets import get_asset_with_deleted
from app.database.crud_users import get_user_by_id
from app.database.crud_asset_types import get_asset_type_by_id
from app.database.crud_vendors import get_vendor_by_id

router_assets = APIRouter(prefix="/assets", tags=["Assets"])


@router_assets.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset_endpoint(
        asset_in: AssetCreate,
        current_user_id: int = 1, # ЗАГЛУШКА: В реальности брать из токена
        db: AsyncSession = Depends(get_db)
):
    """
    Создать новый актив.
    Проверяет уникальность инвентарного и серийного номеров, а также существование родительского актива.
    """
    # 1. Проверка на дубликат inventory_id
    if await check_duplicate_inventory_id(db, asset_in.inventory_id):
        raise HTTPException(status_code=400, detail="Инвентарный номер уже существует")

    # 2. Проверка на дубликат serial_number
    if await check_duplicate_serial_number(db, asset_in.serial_number):
        raise HTTPException(status_code=400, detail="Серийный номер уже существует")

    # 3. Проверка parent_id (если указан)
    if asset_in.parent_id:
        if not await check_parent_exists(db, asset_in.parent_id):
            raise HTTPException(status_code=400, detail="Родительский актив не найден")

    # 4. Проверка на производителя
    if asset_in.manufacturer_id:
        if not await get_vendor_by_id(db, asset_in.manufacturer_id):
            raise HTTPException(status_code=400, detail="Производитель с таким ID не найден")

    # 5. Проверка на поставщика
    if asset_in.vendor_id:
        if not await get_vendor_by_id(db, asset_in.vendor_id):
            raise HTTPException(status_code=400, detail="Поставщик с таким ID не найден")

    # 6. Проверка типа актива
    if asset_in.asset_type_id:
        # if not await get_asset_type(db, asset_in.asset_type_id):
        if not await get_asset_type_by_id(db, asset_in.asset_type_id):
            raise HTTPException(status_code=400, detail="Тип актива не найден")

    if asset_in.prepared_by:
        if not await get_user_by_id(db, asset_in.prepared_by):
            raise HTTPException(status_code=400, detail="Ответственный пользователь с таким ID не найден")

    if asset_in.checked_by:
        if not await get_user_by_id(db, asset_in.checked_by):
            raise HTTPException(status_code=400, detail="Проверяющий пользователь с таким ID не найден")

    # 7. Создание через CRUD
    return await create_asset(db, asset_in, current_user_id=current_user_id)


@router_assets.get("/", response_model=List[AssetShortResponse])
async def get_assets_endpoint(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        asset_status: Optional[str] = None,
        type_id: Optional[int] = None,
        deleted: bool = False,
        db: AsyncSession = Depends(get_db)
):
    """
    Получить список активов с фильтрацией и пагинацией.

    Параметры:
    - skip: пропустить N записей
    - limit: количество записей (макс 100)
    - asset_status: фильтр по статусу
    - type_id: фильтр по типу актива
    - deleted: если True, показывает и удаленные активы
    """
    return await get_assets_list(db, skip, limit, asset_status, type_id, deleted)


@router_assets.get("/{asset_id}", response_model=AssetResponse)
async def get_asset_endpoint(
        asset_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    Получить полную информацию об активе по ID.
    Включает данные о типе актива.
    Возвращает 404, если актив не найден или удален.
    """
    asset = await get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")
    return asset


@router_assets.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset_endpoint(
        asset_id: int,
        asset_data: AssetUpdate,
        current_user_id: int = 1,
        db: AsyncSession = Depends(get_db)
):
    """
    Обновить данные актива.
    Проверяет уникальность изменяемых полей (inventory_id, serial_number).
    """
    # Предварительные проверки перед вызовом CRUD
    current_asset = await get_asset_by_id(db, asset_id)
    if not current_asset:
        raise HTTPException(status_code=404, detail="Актив не найден или удален")

    # Проверка Inventory ID
    if asset_data.inventory_id and asset_data.inventory_id != current_asset.inventory_id:
        if await check_duplicate_inventory_id(db, asset_data.inventory_id, exclude_id=asset_id):
            raise HTTPException(status_code=400, detail="Инвентарный номер уже существует")

    # Проверка Serial Number
    if asset_data.serial_number and asset_data.serial_number != current_asset.serial_number:
        if await check_duplicate_serial_number(db, asset_data.serial_number, exclude_id=asset_id):
            raise HTTPException(status_code=400, detail="Серийный номер уже существует")

    # Проверка Parent ID (если меняется)
    if asset_data.parent_id and asset_data.parent_id != current_asset.parent_id:
        if not await check_parent_exists(db, asset_data.parent_id):
            raise HTTPException(status_code=400, detail="Родительский актив не найден")

        # Защита от циклической ссылки (нельзя сделать родителем самого себя или своего потомка)
        # Для простоты здесь проверяем только ID, полная проверка циклов требует рекурсии
        if asset_data.parent_id == asset_id:
            raise HTTPException(status_code=400, detail="Актив не может быть родителем самого себя")

    updated_asset = await update_asset(db, asset_id, asset_data, current_user_id)
    if not updated_asset:
        raise HTTPException(status_code=404, detail="Ошибка при обновлении")

    return updated_asset


@router_assets.post("/{asset_id}/deactivate", response_model=AssetResponse)
async def deactivate_asset_endpoint(
        asset_id: int,
        current_user_id: int = 1,
        db: AsyncSession = Depends(get_db)
):
    """
    Деактивация актива (мягкое удаление).
    Устанавливает дату удаления, актив скрывается из обычных списков.
    """
    deactivated = await deactivate_asset(db, asset_id, current_user_id)
    if not deactivated:
        raise HTTPException(status_code=404, detail="Актив не найден или уже удален")
    return deactivated


@router_assets.post("/{asset_id}/activate", response_model=AssetResponse)
async def activate_asset_endpoint(
        asset_id: int,
        current_user_id: int = 1,
        db: AsyncSession = Depends(get_db)
):
    """
    Активация актива (восстановление после мягкого удаления).
    """
    activated = await activate_asset(db, asset_id, current_user_id)
    if not activated:
        raise HTTPException(status_code=404, detail="Актив не найден")

    # Если актив уже был активен, CRUD вернет его, но можно добавить проверку в роутере
    if activated.deleted_at is not None:
        raise HTTPException(status_code=400, detail="Не удалось активировать актив")

    return activated


@router_assets.delete("/{asset_id}/hard", status_code=status.HTTP_204_NO_CONTENT)
async def hard_delete_asset_endpoint(
        asset_id: int,
        current_user_id: int = 1,
        db: AsyncSession = Depends(get_db)
):
    """
    Жесткое удаление актива.
    ⚠️ Внимание: Актив должен быть предварительно деактивирован (soft deleted).
    Удаляет актив и всех его дочерних элементов рекурсивно.
    """
    # Проверяем, существует ли актив и удален ли он
    asset = await get_asset_with_deleted(db, asset_id)

    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")

    if asset.deleted_at is None:
        raise HTTPException(
            status_code=400,
            detail="Нельзя жестко удалить актив, который не был деактивирован. Сначала вызовите /deactivate."
        )

    success = await hard_delete_asset(db, asset_id, current_user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Ошибка при удалении актива")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router_assets.get("/{asset_id}/children", response_model=List[AssetShortResponse])
async def get_all_asset_children_endpoint(
        asset_id: int,
        db: AsyncSession = Depends(get_db),
        max_depth: Optional[int] = Query(None, ge=1, le=10, description="Максимальная глубина рекурсии")
):
    """
    Получить ВСЕХ дочерних активов рекурсивно (плоский список).
    Использует PostgreSQL CTE для эффективного построения дерева комплектации.

    Возвращает только активные (не удаленные) дочерние элементы.
    """
    # Проверка существования родителя делается внутри CRUD или здесь
    # Для соблюдения единого стиля, проверим наличие родителя через get_asset_by_id (только активные)
    # Или через get_asset_with_deleted, если хотим видеть детей даже удаленного родителя?
    # По логике ТЗ: родитель должен существовать.

    parent = await get_asset_with_deleted(db, asset_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Родительский актив не найден")

    children_dicts = await get_all_asset_children_recursive(db, asset_id, max_depth)

    # Преобразуем словари в Pydantic модели для валидации ответа
    return [AssetShortResponse(**child) for child in children_dicts]