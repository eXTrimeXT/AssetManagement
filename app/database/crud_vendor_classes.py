from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.VendorClass import VendorClass
from app.schemas.vendors.VendorClassSchemas import VendorClassCreate, VendorClassUpdate


async def get_vendor_class_by_id(db: AsyncSession, class_id: int) -> Optional[VendorClass]:
    result = await db.execute(select(VendorClass).where(VendorClass.class_id == class_id))
    return result.scalar_one_or_none()


async def get_vendor_classes_list(db: AsyncSession, skip: int = 0, limit: int = 50, name: Optional[str] = None) -> Sequence[VendorClass]:
    query = select(VendorClass)
    if name:
        query = query.where(VendorClass.name.ilike(f"%{name}%"))
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def create_vendor_class(db: AsyncSession, class_in: VendorClassCreate, employee_id: str) -> VendorClass:
    db_class = VendorClass(**class_in.model_dump(), created_by=employee_id)
    db.add(db_class)
    await db.commit()
    await db.refresh(db_class)
    return db_class


async def update_vendor_class(db: AsyncSession, class_id: int, class_data: VendorClassUpdate) -> Optional[VendorClass]:
    vendor_class = await get_vendor_class_by_id(db, class_id)
    if not vendor_class:
        return None
    update_data = class_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(vendor_class, key, value)
    await db.commit()
    await db.refresh(vendor_class)
    return vendor_class


async def delete_vendor_class(db: AsyncSession, class_id: int) -> bool:
    vendor_class = await get_vendor_class_by_id(db, class_id)
    if not vendor_class:
        return False
    await db.delete(vendor_class)
    await db.commit()
    return True