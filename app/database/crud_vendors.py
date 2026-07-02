from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.Vendor import Vendor
from app.schemas.vendors.VendorSchemas import VendorCreate, VendorUpdate


async def get_or_create_vendor_by_supplier_number(db: AsyncSession, supplier_number: str, current_user_tab_id) -> int:
    """
    Ищет вендора по supplier_number. Если не находит — создаёт нового с vendor_class_id=1.
    Возвращает vendor_id.
    """
    # Поиск по supplier_number (предполагается, что в модели Vendor есть это поле)
    result = await db.execute(select(Vendor).where(Vendor.name == supplier_number))
    vendor = result.scalar_one_or_none()

    if not vendor:
        # Создаём нового вендора
        new_vendor = Vendor(
            vendor_class_id=1,  # как указано 'поставщик'
            name=supplier_number,  # минимальное имя, можно изменить
            # created_by=current_user_id
            created_by=current_user_tab_id
        )
        db.add(new_vendor)
        await db.commit()
        await db.refresh(new_vendor)
        return new_vendor.vendor_id

    return vendor.vendor_id

async def create_vendor(db: AsyncSession, data: VendorCreate) -> Vendor:
    """Создает нового вендора/поставщика"""
    db_obj = Vendor(**data.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    # Подгружаем связи для ответа
    await db.refresh(db_obj, attribute_names=["vendor_class", "company", "creator"])
    return db_obj


async def get_vendor_by_id(db: AsyncSession, vendor_id: int) -> Optional[Vendor]:
    """Получает вендора по ID со всеми связями"""
    result = await db.execute(
        select(Vendor)
        .where(Vendor.vendor_id == vendor_id)
        .options(
            selectinload(Vendor.vendor_class),
            selectinload(Vendor.company),
            selectinload(Vendor.creator)
        )
    )
    return result.scalar_one_or_none()

async def search_vendors_by_name(db: AsyncSession, name: str) -> Sequence[Vendor]:
    """Поиск вендоров по name (частичное совпадение, без учета регистра)"""
    query = select(Vendor).options(
        selectinload(Vendor.vendor_class),
        selectinload(Vendor.company),
        selectinload(Vendor.creator)
    ).where(Vendor.name.ilike(f"%{name}%"))

    result = await db.execute(query)
    return result.scalars().all()

async def get_vendors_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        vendor_class_id: Optional[int] = None,
        company_id: Optional[int] = None
) -> Sequence[Vendor]:
    """Получает список вендоров с фильтрацией"""
    query = select(Vendor).options(
        selectinload(Vendor.vendor_class),
        selectinload(Vendor.company),
        selectinload(Vendor.creator)
    )

    if vendor_class_id:
        query = query.where(Vendor.vendor_class_id == vendor_class_id)
    if company_id:
        query = query.where(Vendor.company_id == company_id)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def update_vendor(db: AsyncSession, vendor_id: int, data: VendorUpdate) -> Optional[Vendor]:
    """Обновляет данные вендора"""
    obj = await get_vendor_by_id(db, vendor_id)
    if not obj:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(obj, key, value)

    await db.commit()
    await db.refresh(obj)
    await db.refresh(obj, attribute_names=["vendor_class", "company", "creator"])
    return obj


async def delete_vendor(db: AsyncSession, vendor_id: int) -> bool:
    """Удаляет вендора"""
    obj = await get_vendor_by_id(db, vendor_id)
    if not obj:
        return False

    await db.delete(obj)
    await db.commit()
    return True