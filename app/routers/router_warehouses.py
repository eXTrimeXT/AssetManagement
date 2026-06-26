import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database.connection import get_db
from app.schemas.warehouses.WarehouseCreate import WarehouseCreate
from app.schemas.warehouses.WarehouseUpdate import WarehouseUpdate
from app.schemas.warehouses.WarehouseResponse import WarehouseResponse, WarehouseShortResponse

from app.database.crud_warehouses import (
    create_warehouse,
    get_warehouses_list,
    get_warehouse_by_id,
    update_warehouse,
    delete_warehouse,
    check_name_exists,
    search_warehouses_by_name
)
from app.service.auth.auth_service import require_authorized_user

logger = logging.getLogger(__name__)

router_warehouses = APIRouter(prefix="/warehouses", tags=["Warehouses"], dependencies=[Depends(require_authorized_user)])


@router_warehouses.post("/", response_model=WarehouseResponse, status_code=200)
async def create_warehouse_endpoint(warehouse_in: WarehouseCreate, db: AsyncSession = Depends(get_db)):
    """Создать новый склад"""
    if await check_name_exists(db, warehouse_in.name):
        logger.warning("Склад с таким названием уже существует")
        raise HTTPException(status_code=400, detail="Склад с таким названием уже существует")

    # Опционально: можно добавить проверку существования location_id и prepared_by перед созданием
    # if warehouse_in.location_id and not await db.get(Location, warehouse_in.location_id): ...

    return await create_warehouse(db, warehouse_in)

@router_warehouses.get("/", response_model=List[WarehouseShortResponse])
async def get_warehouses_endpoint(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_db)):
    """Получить список всех складов"""
    return await get_warehouses_list(db, skip, limit)

@router_warehouses.get("/search", response_model=List[WarehouseShortResponse])
async def search_warehouses_endpoint(
        name: str = Query(..., min_length=1),
        db: AsyncSession = Depends(get_db)
):
    """Поиск складов по name"""
    return await search_warehouses_by_name(db, name)

@router_warehouses.get("/{warehouse_id}", response_model=WarehouseResponse)
async def get_warehouse_endpoint(warehouse_id: int, db: AsyncSession = Depends(get_db)):
    """Получить полную информацию о складе по ID"""
    warehouse = await get_warehouse_by_id(db, warehouse_id)
    if not warehouse:
        logger.warning("Склад не найден")
        raise HTTPException(status_code=404, detail="Склад не найден")
    return warehouse

@router_warehouses.patch("/{warehouse_id}", response_model=WarehouseResponse)
async def update_warehouse_endpoint(warehouse_id: int, warehouse_data: WarehouseUpdate, db: AsyncSession = Depends(get_db)):
    """Обновить данные склада"""
    # Проверка уникальности имени при обновлении
    if warehouse_data.name:
        current = await get_warehouse_by_id(db, warehouse_id)
        if current and warehouse_data.name != current.name:
            if await check_name_exists(db, warehouse_data.name, exclude_id=warehouse_id):
                logger.warning("Склад с таким названием уже существует")
                raise HTTPException(status_code=400, detail="Склад с таким названием уже существует")

    updated_warehouse = await update_warehouse(db, warehouse_id, warehouse_data)
    if not updated_warehouse:
        logger.warning("Склад не найден")
        raise HTTPException(status_code=404, detail="Склад не найден")
    return updated_warehouse

@router_warehouses.delete("/{warehouse_id}", status_code=200)
async def delete_warehouse_endpoint(warehouse_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить склад"""
    success = await delete_warehouse(db, warehouse_id)
    if not success:
        logger.warning("Склад не найден")
        raise HTTPException(status_code=404, detail="Склад не найден")
    return None