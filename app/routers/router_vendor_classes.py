import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.database.connection import get_db
from app.schemas.vendors.VendorClassSchemas import (
    VendorClassCreate,
    VendorClassUpdate,
    VendorClassResponse,
    VendorClassShortResponse
)
from app.database.crud_vendor_classes import (
    create_vendor_class,
    get_vendor_class_by_id,
    get_vendor_classes_list,
    update_vendor_class,
    delete_vendor_class,
    check_vendor_class_name_exists
)
from app.service.auth.auth_service import require_authorized_user

logger = logging.getLogger(__name__)

router_vendor_classes = APIRouter(prefix="/vendor-classes", tags=["Vendor Classes"], dependencies=[Depends(require_authorized_user)])


@router_vendor_classes.post("/", response_model=VendorClassResponse, status_code=200)
async def create_vendor_class_endpoint(
        data: VendorClassCreate,
        db: AsyncSession = Depends(get_db)
):
    """Создать новый класс вендора/поставщика"""
    if await check_vendor_class_name_exists(db, data.name):
        logger.warning("Класс с таким названием уже существует")
        raise HTTPException(status_code=400, detail="Класс с таким названием уже существует")

    return await create_vendor_class(db, data)


@router_vendor_classes.get("/", response_model=List[VendorClassShortResponse])
async def get_vendor_classes_endpoint(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_db)
):
    """Получить список всех классов вендоров/поставщиков"""
    return await get_vendor_classes_list(db, skip, limit)


@router_vendor_classes.get("/{vendor_class_id}", response_model=VendorClassResponse)
async def get_vendor_class_endpoint(
        vendor_class_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Получить класс по ID"""
    obj = await get_vendor_class_by_id(db, vendor_class_id)
    if not obj:
        logger.warning("Класс не найден")
        raise HTTPException(status_code=404, detail="Класс не найден")
    return obj


@router_vendor_classes.patch("/{vendor_class_id}", response_model=VendorClassResponse)
async def update_vendor_class_endpoint(
        vendor_class_id: int,
        data: VendorClassUpdate,
        db: AsyncSession = Depends(get_db)
):
    """Обновить данные класса"""
    if data.name:
        current = await get_vendor_class_by_id(db, vendor_class_id)
        if current and data.name != current.name:
            if await check_vendor_class_name_exists(db, data.name, exclude_id=vendor_class_id):
                logger.warning("Класс с таким названием уже существует")
                raise HTTPException(status_code=400, detail="Класс с таким названием уже существует")

    updated_obj = await update_vendor_class(db, vendor_class_id, data)
    if not updated_obj:
        logger.warning("Класс не найден")
        raise HTTPException(status_code=404, detail="Класс не найден")
    return updated_obj


@router_vendor_classes.delete("/{vendor_class_id}", status_code=200)
async def delete_vendor_class_endpoint(
        vendor_class_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Удалить класс"""
    success = await delete_vendor_class(db, vendor_class_id)
    if not success:
        logger.warning("Класс не найден")
        raise HTTPException(status_code=404, detail="Класс не найден")
    return None