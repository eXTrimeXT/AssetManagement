from typing import Optional, Sequence, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.VendorClass import VendorClass
from app.schemas.vendors.VendorClassSchemas import VendorClassCreate, VendorClassUpdate


async def check_vendor_class_name_exists(db: AsyncSession, name: str, exclude_id: Optional[int] = None) -> bool:
    """Проверяет уникальность названия класса"""
    query = select(VendorClass).where(VendorClass.name == name)
    if exclude_id:
        query = query.where(VendorClass.vendor_class_id != exclude_id)
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None


async def create_vendor_class(db: AsyncSession, data: VendorClassCreate) -> VendorClass:
    """Создает новый класс вендора/поставщика"""
    db_obj = VendorClass(**data.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def get_vendor_class_by_id(db: AsyncSession, vendor_class_id: int) -> type[VendorClass] | Any:
    """Получает класс по ID"""
    return await db.get(VendorClass, vendor_class_id)


async def get_vendor_classes_list(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[VendorClass]:
    """Получает список всех классов"""
    query = select(VendorClass).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_vendor_class(db: AsyncSession, vendor_class_id: int, data: VendorClassUpdate) -> type[VendorClass] | None | Any:
    """Обновляет данные класса"""
    obj = await get_vendor_class_by_id(db, vendor_class_id)
    if not obj:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(obj, key, value)

    await db.commit()
    await db.refresh(obj)
    return obj


async def delete_vendor_class(db: AsyncSession, vendor_class_id: int) -> bool:
    """Удаляет класс"""
    obj = await get_vendor_class_by_id(db, vendor_class_id)
    if not obj:
        return False

    await db.delete(obj)
    await db.commit()
    return True