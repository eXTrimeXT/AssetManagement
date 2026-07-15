from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.database.map_assets.crud_workshop import (
    create_workshop, get_workshop, get_all_workshop, get_workshop_by_code,
    delete_workshop, update_workshop, hard_delete_workshop
)
from app.schemas.map_assets.WorkshopCreate import WorkshopCreate
from app.schemas.map_assets.WorkshopUpdate import WorkshopUpdate
from app.schemas.map_assets.WorkshopResponse import WorkshopResponse

router_workshop = APIRouter(prefix="/workshops", tags=["workshops"])

@router_workshop.post(
    "/",
    response_model=WorkshopResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый цех",
    description="Создает новый цех с указанными параметрами"
)
async def endpoint_create_workshop(
        workshop_data: WorkshopCreate,
        db: AsyncSession = Depends(get_db)
):
    """Создать новый цех"""
    # Проверка уникальности кода
    isExisting = await get_workshop_by_code(db, workshop_data.code)
    if isExisting:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Цех с кодом '{workshop_data.code}' уже существует"
        )
    return await create_workshop(db, workshop_data)


@router_workshop.get(
    "/",
    response_model=List[WorkshopResponse],
    summary="Получить все цеха",
    description="Возвращает список всех активных цехов"
)
async def endpoint_get_all_workshops(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db)
):
    """Получить список всех цехов"""
    workshops = await get_all_workshop(db, skip=skip, limit=limit)
    return workshops


@router_workshop.get(
    "/{workshop_id}",
    response_model=WorkshopResponse,
    summary="Получить цех по ID",
    description="Возвращает информацию о цехе по его ID"
)
async def endpoint_get_workshop(
        workshop_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Получить цех по ID"""
    workshop = await get_workshop(db, workshop_id)
    if not workshop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Цех с ID {workshop_id} не найден"
        )
    return workshop


@router_workshop.put(
    "/{workshop_id}",
    response_model=WorkshopResponse,
    summary="Обновить цех",
    description="Обновляет информацию о цехе"
)
async def endpoint_update_workshop(
        workshop_id: int,
        workshop_data: WorkshopUpdate,
        db: AsyncSession = Depends(get_db)
):
    """Обновить цех"""
    # Проверка существования
    workshop = await get_workshop(db, workshop_id)
    if not workshop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Цех с ID {workshop_id} не найден"
        )
    # Проверка уникальности кода, если он меняется
    if workshop_data.code and workshop_data.code != workshop.code:
        existing = await get_workshop_by_code(db, str(workshop_data.code))
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Цех с кодом '{workshop_data.code}' уже существует"
            )

    updated_workshop = await update_workshop(db, workshop_id, workshop_data)
    return updated_workshop


@router_workshop.delete(
    "/{workshop_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить цех (мягкое удаление)",
    description="Помечает цех как неактивный"
)
async def endpoint_delete_workshop(
        workshop_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Мягкое удаление цеха"""
    workshop = await get_workshop(db, workshop_id)
    if not workshop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Цех с ID {workshop_id} не найден"
        )
    await delete_workshop(db, workshop_id)
    return None


@router_workshop.delete(
    "/{workshop_id}/hard",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Полностью удалить цех",
    description="Полностью удаляет цех из базы данных (необратимо)"
)
async def endpoint_hard_delete_workshop(
        workshop_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Полное удаление цеха"""
    workshop = await get_workshop(db, workshop_id)
    if not workshop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Цех с ID {workshop_id} не найден"
        )
    await hard_delete_workshop(db, workshop_id)
    return None