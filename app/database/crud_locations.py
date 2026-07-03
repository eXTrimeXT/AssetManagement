from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.Location import Location
from app.schemas.locations.LocationCreate import LocationCreate
from app.schemas.locations.LocationUpdate import LocationUpdate


async def get_location_by_id(db: AsyncSession, location_id: int) -> Optional[Location]:
    """Получить локацию по ID с загруженным creator"""
    result = await db.execute(
        select(Location)
        .options(selectinload(Location.creator))
        .where(Location.location_id == location_id)
    )
    return result.scalar_one_or_none()


async def get_locations_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        name: Optional[str] = None,
        country: Optional[str] = None,
        city: Optional[str] = None,
) -> Sequence[Location]:
    """Получить список локаций с фильтрами"""
    query = select(Location).options(selectinload(Location.creator))

    if name:
        query = query.where(Location.name.ilike(f"%{name}%"))
    if country:
        query = query.where(Location.country.ilike(f"%{country}%"))
    if city:
        query = query.where(Location.city.ilike(f"%{city}%"))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def create_location(db: AsyncSession, location_in: LocationCreate, employee_id: str) -> Location:
    """Создать новую локацию"""
    db_location = Location(**location_in.model_dump(), created_by=employee_id)
    db.add(db_location)
    await db.commit()
    # Перезагружаем с creator для корректной сериализации
    return await get_location_by_id(db, db_location.location_id)


async def update_location(db: AsyncSession, location_id: int, location_data: LocationUpdate) -> Optional[Location]:
    """Обновить локацию"""
    location = await get_location_by_id(db, location_id)
    if not location:
        return None
    update_data = location_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(location, key, value)
    await db.commit()
    # Перезагружаем с creator
    return await get_location_by_id(db, location_id)


async def delete_location(db: AsyncSession, location_id: int) -> bool:
    """Удалить локацию"""
    location = await get_location_by_id(db, location_id)
    if not location:
        return False
    await db.delete(location)
    await db.commit()
    return True