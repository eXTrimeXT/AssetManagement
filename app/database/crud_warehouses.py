from typing import List, Optional, Sequence, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.Warehouse import Warehouse
from app.schemas.warehouses.WarehouseCreate import WarehouseCreate
from app.schemas.warehouses.WarehouseUpdate import WarehouseUpdate


async def check_name_exists(db: AsyncSession, name: str, exclude_id: Optional[int] = None) -> bool:
    """Проверяет уникальность названия склада"""
    query = select(Warehouse).where(Warehouse.name == name)
    if exclude_id:
        query = query.where(Warehouse.warehouse_id != exclude_id)
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None


async def get_warehouse_by_id(db: AsyncSession, warehouse_id: int) -> Optional[Warehouse]:
    """Получает склад по ID с подгрузкой связей"""
    result = await db.execute(
        select(Warehouse)
        .where(Warehouse.warehouse_id == warehouse_id)
        .options(selectinload(Warehouse.location), selectinload(Warehouse.preparer))
    )
    return result.scalar_one_or_none()


async def create_warehouse(db: AsyncSession, warehouse_in: WarehouseCreate) -> Warehouse:
    """Создает новый склад"""
    db_warehouse = Warehouse(**warehouse_in.model_dump())
    db.add(db_warehouse)
    await db.commit()
    await db.refresh(db_warehouse)
    # Подгружаем связи сразу после создания для возврата полного объекта
    await db.refresh(db_warehouse, attribute_names=["location", "preparer"])
    return db_warehouse


async def get_warehouses_list(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[Any]:
    """Получает список складов"""
    query = select(Warehouse).options(
        selectinload(Warehouse.location),
        selectinload(Warehouse.preparer)
    )
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_warehouse(db: AsyncSession, warehouse_id: int, warehouse_data: WarehouseUpdate) -> Optional[Warehouse]:
    """Обновляет данные склада"""
    warehouse = await get_warehouse_by_id(db, warehouse_id)
    if not warehouse:
        return None

    update_data = warehouse_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(warehouse, key, value)

    await db.commit()
    await db.refresh(warehouse)
    await db.refresh(warehouse, attribute_names=["location", "preparer"])
    return warehouse


async def delete_warehouse(db: AsyncSession, warehouse_id: int) -> bool:
    """Удаляет склад"""
    warehouse = await get_warehouse_by_id(db, warehouse_id)
    if not warehouse:
        return False

    await db.delete(warehouse)
    await db.commit()
    return True