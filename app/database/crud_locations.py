from typing import Optional, Sequence, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.Location import Location
from app.schemas.locations.LocationCreate import LocationCreate
from app.schemas.locations.LocationUpdate import LocationUpdate


# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
async def get_location_by_id(db: AsyncSession, location_id: int) -> Optional[Location]:
    """ Получает локацию по ID """
    result = await db.execute(
        select(Location).where(Location.location_id == location_id)
    )
    return result.scalar_one_or_none()


# CRUD ОПЕРАЦИИ
async def create_location(db: AsyncSession, location_in: LocationCreate) -> Location:
    """ Создает новую запись о локации """
    db_location = Location(**location_in.model_dump())
    db.add(db_location)
    await db.commit()
    await db.refresh(db_location)
    return db_location

async def get_locations_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        city: Optional[str] = None,
        country: Optional[str] = None
) -> Sequence[Any]:
    """ Получает список локаций с фильтрацией и пагинацией """
    query = select(Location)

    if city:
        query = query.where(Location.city.ilike(f"%{city}%"))

    if country:
        query = query.where(Location.country.ilike(f"%{country}%"))

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

async def update_location(
        db: AsyncSession,
        location_id: int,
        location_data: LocationUpdate
) -> Optional[Location]:
    """ Обновляет данные локации """
    location = await get_location_by_id(db, location_id)
    if not location:
        return None

    update_data = location_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(location, key, value)

    await db.commit()
    await db.refresh(location)
    return location

async def delete_location(db: AsyncSession, location_id: int) -> bool:
    """
    Удаляет локацию.
    Возвращает True при успешном удалении.
    """
    location = await get_location_by_id(db, location_id)
    if not location:
        return False

    await db.delete(location)
    await db.commit()
    return True