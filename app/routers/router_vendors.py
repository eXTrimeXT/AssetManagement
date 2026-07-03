import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database.connection import get_db
from app.database.crud_vendors import (
    get_vendor_by_id, get_vendors_list, create_vendor, update_vendor, delete_vendor
)
from app.schemas.vendors.VendorSchemas import VendorCreate, VendorUpdate, VendorResponse
from app.services.auth.auth_service import require_authorized_user

logger = logging.getLogger(__name__)
router_vendors = APIRouter(prefix="/vendors", tags=["Vendors"])


@router_vendors.get("/", response_model=List[VendorResponse])
async def get_vendors(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        name: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    return await get_vendors_list(db, skip, limit, name)


@router_vendors.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor(
        vendor_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    vendor = await get_vendor_by_id(db, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    return vendor


@router_vendors.post("/", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor_endpoint(
        vendor_in: VendorCreate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    return await create_vendor(db, vendor_in, current_user.employee_id)


@router_vendors.patch("/{vendor_id}", response_model=VendorResponse)
async def update_vendor_endpoint(
        vendor_id: int,
        vendor_data: VendorUpdate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    updated = await update_vendor(db, vendor_id, vendor_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    return updated


@router_vendors.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor_endpoint(
        vendor_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    success = await delete_vendor(db, vendor_id)
    if not success:
        raise HTTPException(status_code=404, detail="Поставщик не найден")