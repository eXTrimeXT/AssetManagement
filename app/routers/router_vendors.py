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
    delete_vendor
)

router_vendors = APIRouter(prefix="/vendors", tags=["Vendors & Suppliers"])


@router_vendors.post("/", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor_endpoint(
        data: VendorCreate,
        db: AsyncSession = Depends(get_db)
):
    """Создать нового вендора/поставщика"""
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
    """Получить список вендоров/поставщиков с фильтрацией"""
    return await get_vendors_list(db, skip, limit, vendor_class_id, company_id)


@router_vendors.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor_endpoint(
        vendor_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Получить вендора по ID"""
    obj = await get_vendor_by_id(db, vendor_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Вендор не найден")
    return obj


@router_vendors.patch("/{vendor_id}", response_model=VendorResponse)
async def update_vendor_endpoint(
        vendor_id: int,
        data: VendorUpdate,
        db: AsyncSession = Depends(get_db)
):
    """Обновить данные вендора"""
    updated_obj = await update_vendor(db, vendor_id, data)
    if not updated_obj:
        raise HTTPException(status_code=404, detail="Вендор не найден")
    return updated_obj


@router_vendors.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor_endpoint(
        vendor_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Удалить вендора"""
    success = await delete_vendor(db, vendor_id)
    if not success:
        raise HTTPException(status_code=404, detail="Вендор не найден")
    return None