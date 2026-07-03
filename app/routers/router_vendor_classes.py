import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database.connection import get_db
from app.database.crud_vendor_classes import (
    get_vendor_class_by_id, get_vendor_classes_list, create_vendor_class, update_vendor_class, delete_vendor_class
)
from app.schemas.vendors.VendorClassSchemas import VendorClassCreate, VendorClassUpdate, VendorClassResponse
from app.services.auth.auth_service import require_authorized_user

logger = logging.getLogger(__name__)
router_vendor_classes = APIRouter(prefix="/vendor-classes", tags=["Vendor Classes"])


@router_vendor_classes.get("/", response_model=List[VendorClassResponse])
async def get_vendor_classes(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        name: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    return await get_vendor_classes_list(db, skip, limit, name)


@router_vendor_classes.get("/{class_id}", response_model=VendorClassResponse)
async def get_vendor_class(
        class_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    vendor_class = await get_vendor_class_by_id(db, class_id)
    if not vendor_class:
        raise HTTPException(status_code=404, detail="Класс поставщика не найден")
    return vendor_class


@router_vendor_classes.post("/", response_model=VendorClassResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor_class_endpoint(
        class_in: VendorClassCreate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    return await create_vendor_class(db, class_in, current_user.employee_id)


@router_vendor_classes.patch("/{class_id}", response_model=VendorClassResponse)
async def update_vendor_class_endpoint(
        class_id: int,
        class_data: VendorClassUpdate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    updated = await update_vendor_class(db, class_id, class_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Класс поставщика не найден")
    return updated


@router_vendor_classes.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor_class_endpoint(
        class_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    success = await delete_vendor_class(db, class_id)
    if not success:
        raise HTTPException(status_code=404, detail="Класс поставщика не найден")