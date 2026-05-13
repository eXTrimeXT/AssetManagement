from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional

from app.database.connection import get_db
from app.schemas.locations.LocationResponse import LocationResponse, LocationShortResponse

# Импорт CRUD функций
from app.database.crud_locations import *
from app.service.auth.auth_service import require_authorized_user

router_locations = APIRouter(prefix="/locations", tags=["Locations"], dependencies=[Depends(require_authorized_user)])


@router_locations.post("/", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location_endpoint(
        location_in: LocationCreate,
        db: AsyncSession = Depends(get_db)
):
    """Создать новую локацию"""
    return await create_location(db, location_in)


@router_locations.get("/", response_model=List[LocationShortResponse])
async def get_locations_endpoint(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        city: Optional[str] = None,
        country: Optional[str] = None,
        db: AsyncSession = Depends(get_db)
):
    """Получить список локаций с фильтрацией по городу и стране"""
    return await get_locations_list(db, skip, limit, city, country)


@router_locations.get("/{location_id}", response_model=LocationResponse)
async def get_location_endpoint(
        location_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Получить полную информацию о локации по ID"""
    location = await get_location_by_id(db, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Локация не найдена")
    return location


@router_locations.patch("/{location_id}", response_model=LocationResponse)
async def update_location_endpoint(
        location_id: int,
        location_data: LocationUpdate,
        db: AsyncSession = Depends(get_db)
):
    """Обновить данные локации"""
    updated_location = await update_location(db, location_id, location_data)
    if not updated_location:
        raise HTTPException(status_code=404, detail="Локация не найдена")
    return updated_location


@router_locations.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location_endpoint(
        location_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Удалить локацию"""
    success = await delete_location(db, location_id)
    if not success:
        raise HTTPException(status_code=404, detail="Локация не найдена")
    return None