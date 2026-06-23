import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database.connection import get_db
from app.schemas.vendors.VendorSchemas import (
    VendorCreate,
    VendorUpdate,
    VendorResponse,
    VendorShortResponse
)
from app.database.crud_vendors import (
    create_vendor,
    get_vendor_by_id,
    get_vendors_list,
    update_vendor,
    delete_vendor,
    search_vendors_by_name
)
from app.service.auth.auth_service import require_authorized_user

logger = logging.getLogger(__name__)

router_vendors = APIRouter(prefix="/vendors", tags=["Vendors & Suppliers"], dependencies=[Depends(require_authorized_user)])


@router_vendors.post("/", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor_endpoint(
        data: VendorCreate,
        db: AsyncSession = Depends(get_db)
):
    """Создать нового Продавца/поставщика"""
    # Можно добавить проверки существования vendor_class_id и company_id перед созданием
    return await create_vendor(db, data)


@router_vendors.get("/", response_model=List[VendorShortResponse])
async def get_vendors_endpoint(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        vendor_class_id: Optional[int] = None,
        company_id: Optional[int] = None,
        db: AsyncSession = Depends(get_db)
):
    """Получить список продавцов/поставщиков с фильтрацией"""
    return await get_vendors_list(db, skip, limit, vendor_class_id, company_id)

@router_vendors.get("/search", response_model=List[VendorShortResponse])
async def search_vendors_endpoint(
        name: str = Query(..., min_length=1),
        db: AsyncSession = Depends(get_db)
):
    """Поиск продавцов/поставщиков по name"""
    return await search_vendors_by_name(db, name)

@router_vendors.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor_endpoint(
        vendor_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Получить продавца по ID"""
    obj = await get_vendor_by_id(db, vendor_id)
    if not obj:
        logger.warning("Продавец не найден")
        raise HTTPException(status_code=404, detail="Продавец не найден")
    return obj


@router_vendors.patch("/{vendor_id}", response_model=VendorResponse)
async def update_vendor_endpoint(
        vendor_id: int,
        data: VendorUpdate,
        db: AsyncSession = Depends(get_db)
):
    """Обновить данные продавца"""
    updated_obj = await update_vendor(db, vendor_id, data)
    if not updated_obj:
        logger.warning("Продавец не найден")
        raise HTTPException(status_code=404, detail="Продавец не найден")
    return updated_obj


@router_vendors.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor_endpoint(
        vendor_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Удалить продавца"""
    success = await delete_vendor(db, vendor_id)
    if not success:
        logger.warning("Продавец не найден")
        raise HTTPException(status_code=404, detail="Продавец не найден")
    return None