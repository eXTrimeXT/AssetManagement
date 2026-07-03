import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database.connection import get_db
from app.database.crud_locations import (
    get_location_by_id, get_locations_list, create_location, update_location, delete_location
)
from app.schemas.locations.LocationCreate import LocationCreate
from app.schemas.locations.LocationUpdate import LocationUpdate
from app.schemas.locations.LocationResponse import LocationResponse
from app.services.auth.auth_service import require_authorized_user

logger = logging.getLogger(__name__)
router_locations = APIRouter(prefix="/locations", tags=["Locations"])


@router_locations.get("/", response_model=List[LocationResponse])
async def get_locations(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        name: Optional[str] = Query(None),
        country: Optional[str] = Query(None),
        city: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    return await get_locations_list(db, skip, limit, name, country, city)


@router_locations.get("/{location_id}", response_model=LocationResponse)
async def get_location(
        location_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    location = await get_location_by_id(db, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Локация не найдена")
    return location


@router_locations.post("/", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location_endpoint(
        location_in: LocationCreate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    return await create_location(db, location_in, current_user.employee_id)


@router_locations.patch("/{location_id}", response_model=LocationResponse)
async def update_location_endpoint(
        location_id: int,
        location_data: LocationUpdate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    updated = await update_location(db, location_id, location_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Локация не найдена")
    return updated


@router_locations.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location_endpoint(
        location_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    success = await delete_location(db, location_id)
    if not success:
        raise HTTPException(status_code=404, detail="Локация не найдена")