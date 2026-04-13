from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from typing import Optional, List, Any
from app.database.connection import get_db
from app.models.Asset import Asset
from app.schemas.assets.AssetCreate import AssetCreate
from app.schemas.assets.AssetUpdate import AssetUpdate
from app.schemas.assets.AssetResponse import AssetResponse, AssetShortResponse

router_assets = APIRouter(prefix="/assets", tags=["Assets"])

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

async def _get_active_asset(asset_id: int, db: AsyncSession) -> Any | None:
    """Получить актив (только не удалённые)"""
    result = await db.execute(
        select(Asset)
        .where(Asset.asset_id == asset_id)
        .where(Asset.deleted_at.is_(None))
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")
    return asset


async def _get_asset_with_deleted(asset_id: int, db: AsyncSession) -> Any | None:
    """Получить актив (включая удалённые)"""
    result = await db.execute(
        select(Asset)
        .where(Asset.asset_id == asset_id)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")
    return asset


# =============================================================================
# === CRUD ОПЕРАЦИИ ===
# =============================================================================

@router_assets.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(asset_in: AssetCreate, db: AsyncSession = Depends(get_db)):
    """Создать новый актив"""
    # Проверка на дубликат inventory_id
    result = await db.execute(select(Asset).where(Asset.inventory_id == asset_in.inventory_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Инвентарный номер уже существует")

    # Проверка на дубликат serial_number
    result = await db.execute(select(Asset).where(Asset.serial_number == asset_in.serial_number))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Серийный номер уже существует")

    # Проверка parent_id (если указан)
    if asset_in.parent_id:
        parent = await db.get(Asset, asset_in.parent_id)
        if not parent:
            raise HTTPException(status_code=400, detail="Родительский актив не найден")

    db_asset = Asset(**asset_in.model_dump())
    db.add(db_asset)
    await db.commit()
    await db.refresh(db_asset)
    return db_asset


@router_assets.get("/", response_model=List[AssetShortResponse])
async def get_assets(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        asset_status: Optional[str] = None,
        type_id: Optional[int] = None,
        location: Optional[str] = None,
        deleted: bool = False,
        db: AsyncSession = Depends(get_db)
):
    """Получить список активов с фильтрацией"""
    query = select(Asset)

    if not deleted:
        query = query.where(Asset.deleted_at.is_(None))

    if asset_status:
        query = query.where(Asset.asset_status == asset_status)
    if type_id:
        query = query.where(Asset.type_id == type_id)
    if location:
        query = query.where(Asset.location.ilike(f"%{location}%"))

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router_assets.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: int, db: AsyncSession = Depends(get_db)):
    """Получить актив по ID с комплектацией (children)"""
    result = await db.execute(
        select(Asset)
        .where(Asset.asset_id == asset_id)
        .where(Asset.deleted_at.is_(None))
        .options(selectinload(Asset.asset_type))
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")
    return asset


@router_assets.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset(asset_id: int, asset_data: AssetUpdate, db: AsyncSession = Depends(get_db)):
    """Обновить данные актива"""
    asset = await _get_active_asset(asset_id, db)

    # Проверка на дубликат inventory_id при обновлении
    if asset_data.inventory_id and asset_data.inventory_id != asset.inventory_id:
        existing = await db.execute(select(Asset).where(Asset.inventory_id == asset_data.inventory_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Инвентарный номер уже существует")

    # Проверка на дубликат serial_number
    if asset_data.serial_number and asset_data.serial_number != asset.serial_number:
        existing = await db.execute(select(Asset).where(Asset.serial_number == asset_data.serial_number))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Серийный номер уже существует")

    update_data = asset_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(asset, key, value)

    await db.commit()
    await db.refresh(asset)
    return asset


# =============================================================================
# === УПРАВЛЕНИЕ СТАТУСОМ АКТИВА (3 ручки) ===
# =============================================================================

@router_assets.post("/{asset_id}/deactivate", response_model=AssetResponse)
async def deactivate_asset(asset_id: int, db: AsyncSession = Depends(get_db)):
    """
    Деактивация актива (мягкое удаление).
    Устанавливает deleted_at и скрывает из обычных списков.
    """
    asset = await _get_active_asset(asset_id, db)

    asset.deleted_at = datetime.now()
    asset.updated_at = datetime.now()

    await db.commit()
    await db.refresh(asset)

    return asset


@router_assets.post("/{asset_id}/activate", response_model=AssetResponse)
async def activate_asset(asset_id: int, db: AsyncSession = Depends(get_db)):
    """
    Активация актива (восстановление после мягкого удаления).
    """
    asset = await _get_asset_with_deleted(asset_id, db)

    if asset.deleted_at is None:
        raise HTTPException(status_code=400, detail="Актив уже активен")

    asset.deleted_at = None
    asset.updated_at = datetime.now()

    await db.commit()
    await db.refresh(asset)

    return asset


@router_assets.delete("/{asset_id}/hard", status_code=status.HTTP_204_NO_CONTENT)
async def hard_delete_asset(asset_id: int, db: AsyncSession = Depends(get_db)):
    """
    Жесткое удаление актива с каскадным удалением дочерних элементов.

    ⚠️ Требования:
    - Актив должен быть деактивирован (deleted_at != NULL)
    - Не должно быть дочерних активов (или они тоже должны быть деактивированы)
    """
    asset = await _get_asset_with_deleted(asset_id, db)

    # Проверка: актив должен быть деактивирован
    if asset.deleted_at is None:
        raise HTTPException(
            status_code=400,
            detail="Нельзя жестко удалить актив, который не был деактивирован. Сначала вызовите deactivate."
        )

    # Сбор всех ID активов (родитель + дети рекурсивно)
    async def collect_child_ids(parent_id: int) -> list[int]:
        result = await db.execute(select(Asset.asset_id).where(Asset.parent_id == parent_id))
        child_ids = [row[0] for row in result.fetchall()]
        all_ids = child_ids.copy()
        for child_id in child_ids:
            all_ids.extend(await collect_child_ids(child_id))
        return all_ids

    child_ids = await collect_child_ids(asset_id)
    all_ids = [asset_id] + child_ids

    # Удаляем дочерние активы (каскадно)
    if child_ids:
        child_ids.reverse()  # От листьев к корню
        await db.execute(delete(Asset).where(Asset.asset_id.in_(child_ids)))

    # Удаляем основной актив
    await db.delete(asset)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Рекурсивное получение всех детей
@router_assets.get("/{asset_id}/children", response_model=List[AssetShortResponse])
async def get_all_asset_children(
        asset_id: int,
        db: AsyncSession = Depends(get_db),
        max_depth: Optional[int] = Query(None, ge=1, le=10, description="Максимальная глубина рекурсии")
):
    """
    Получить ВСЕХ дочерних активов рекурсивно (всё дерево комплектации).

    Использует рекурсивный CTE-запрос PostgreSQL для эффективности.

    Параметры:
    - `asset_id`: ID родительского актива
    - `max_depth`: Ограничение глубины рекурсии (1-10, опционально)

    Возвращает:
    - Плоский список всех потомков (без вложенности)
    """
    # 1. Проверяем существование родителя
    parent = await db.get(Asset, asset_id)
    if not parent or parent.deleted_at:
        raise HTTPException(status_code=404, detail="Актив не найден")

    # 2. Рекурсивный CTE-запрос для получения всех потомков
    # Используем raw SQL через text() для рекурсивного WITH-запроса
    recursive_query = text("""
                           WITH RECURSIVE asset_tree AS (
                               -- Базовый случай: прямые дети указанного актива
                               SELECT
                                   asset_id, name, inventory_id, serial_number, asset_status, type_id,
                                   location, parent_id, deleted_at, software_id,  1 AS depth
                               FROM assets
                               WHERE parent_id = :root_id AND deleted_at IS NULL

                               UNION ALL

                               -- Рекурсивный случай: дети детей
                               SELECT
                                   a.asset_id, a.name, a.inventory_id, a.serial_number, a.asset_status, a.type_id,
                                   a.location, a.parent_id, a.deleted_at, a.software_id, at.depth + 1
                               FROM assets a
                                        INNER JOIN asset_tree at ON a.parent_id = at.asset_id
                           WHERE a.deleted_at IS NULL
                               {% if max_depth %}AND at.depth < :max_depth{% endif %}
                               )
                           SELECT * FROM asset_tree
                           ORDER BY depth, asset_id
                           """)

    # 3. Подготовка параметров запроса
    params = {"root_id": asset_id}
    if max_depth:
        params["max_depth"] = max_depth
        # Заменяем плейсхолдер в запросе
        query_str = recursive_query.text.replace(
            "{% if max_depth %}AND at.depth < :max_depth{% endif %}",
            "AND at.depth < :max_depth"
        )
        final_query = text(query_str)
    else:
        # Убираем условие макс. глубины
        query_str = recursive_query.text.replace(
            "{% if max_depth %}AND at.depth < :max_depth{% endif %}",
            ""
        )
        final_query = text(query_str)

    # 4. Выполнение запроса
    result = await db.execute(final_query, params)
    rows = result.fetchall()

    # 5. Конвертация результатов в словари для Pydantic
    children = []
    for row in rows:
        # Row: (asset_id, name, inventory_id, serial_number, asset_status, type_id, location, parent_id, deleted_at, depth)
        children.append({
            "asset_id": row.asset_id,
            "name": row.name,
            "inventory_id": row.inventory_id,
            "serial_number": row.serial_number,
            "asset_status": row.asset_status,
            "type_id": row.type_id,
            "location": row.location,
            "parent_id": row.parent_id,
            "software_id": row.parent_id,
        })

    return children
