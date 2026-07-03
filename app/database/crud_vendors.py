from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.Vendor import Vendor
from app.models.zup.employee import Employee
from app.models.Company import Company
from app.schemas.vendors.VendorSchemas import VendorCreate, VendorUpdate


async def get_vendor_by_id(db: AsyncSession, vendor_id: int) -> Optional[Vendor]:
    result = await db.execute(
        select(Vendor)
        .options(
            selectinload(Vendor.company).options(
                selectinload(Company.location_obj),
                selectinload(Company.creator)
            ),
            selectinload(Vendor.vendor_class),
            selectinload(Vendor.creator)
        )
        .where(Vendor.vendor_id == vendor_id)
    )
    return result.scalar_one_or_none()


async def get_vendors_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        name: Optional[str] = None
) -> Sequence[Vendor]:
    query = select(Vendor).options(
        selectinload(Vendor.company).options(
            selectinload(Company.location_obj),
            selectinload(Company.creator)
        ),
        selectinload(Vendor.vendor_class),
        selectinload(Vendor.creator)
    )
    if name:
        query = query.where(Vendor.name.ilike(f"%{name}%"))
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def create_vendor(db: AsyncSession, vendor_in: VendorCreate, employee_id: str) -> Vendor:
    db_vendor = Vendor(**vendor_in.model_dump(), created_by=employee_id)
    db.add(db_vendor)
    await db.commit()
    # Перезагружаем через get_vendor_by_id с selectinload
    return await get_vendor_by_id(db, db_vendor.vendor_id)


async def update_vendor(db: AsyncSession, vendor_id: int, vendor_data: VendorUpdate) -> Optional[Vendor]:
    vendor = await get_vendor_by_id(db, vendor_id)
    if not vendor:
        return None
    update_data = vendor_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(vendor, key, value)
    await db.commit()
    # Перезагружаем с полными связями
    return await get_vendor_by_id(db, vendor_id)


async def delete_vendor(db: AsyncSession, vendor_id: int) -> bool:
    vendor = await get_vendor_by_id(db, vendor_id)
    if not vendor:
        return False
    await db.delete(vendor)
    await db.commit()
    return True