from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.database import crud_workshop
from app.schemas.workshop.Workshop import (
    WorkshopCreate,
    WorkshopUpdate,
    WorkshopResponse,
    WorkshopListResponse
)

router_workshop = APIRouter(prefix="/workshops", tags=["Workshops"])


@router_workshop.post("/", response_model=WorkshopResponse, status_code=201)
async def create_workshop(
        data: WorkshopCreate,
        db: AsyncSession = Depends(get_db)
):
    """
    Создание нового цеха.
    """
    try:
        workshop = await crud_workshop.create_workshop(db, data)
        return workshop
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router_workshop.get("/", response_model=List[WorkshopListResponse])
async def get_workshops(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        db: AsyncSession = Depends(get_db)
):
    """
    Получение списка всех цехов с пагинацией.
    """
    workshops = await crud_workshop.get_workshops(db, skip=skip, limit=limit)
    return workshops


@router_workshop.get("/{workshop_id}", response_model=WorkshopResponse)
async def get_workshop(
        workshop_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    Получение информации о цехе по ID.
    """
    workshop = await crud_workshop.get_workshop(db, workshop_id)
    if not workshop:
        raise HTTPException(status_code=404, detail="Workshop not found")
    return workshop


@router_workshop.patch("/{workshop_id}", response_model=WorkshopResponse)
async def update_workshop(
        workshop_id: int,
        data: WorkshopUpdate,
        db: AsyncSession = Depends(get_db)
):
    """
    Обновление данных цеха.
    """
    try:
        workshop = await crud_workshop.update_workshop(db, workshop_id, data)
        if not workshop:
            raise HTTPException(status_code=404, detail="Workshop not found")
        return workshop
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router_workshop.delete("/{workshop_id}", status_code=204)
async def delete_workshop(
        workshop_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    Удаление цеха.
    """
    success = await crud_workshop.delete_workshop(db, workshop_id)
    if not success:
        raise HTTPException(status_code=404, detail="Workshop not found")
    return None