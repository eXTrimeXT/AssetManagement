from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.database.connection import get_db
from app.schemas.software.SoftwareCreate import SoftwareCreate
from app.schemas.software.SoftwareUpdate import SoftwareUpdate
from app.schemas.software.SoftwareResponse import SoftwareResponse, SoftwareShortResponse
from app.schemas.assets.AssetResponse import AssetShortResponse

# Импорт CRUD функций
from app.database.crud_software import (
    create_software,
    get_software_list,
    get_software_by_id,
    update_software,
    delete_software,
    check_software_has_assets,
    get_assets_by_software_id
)

router_software = APIRouter(prefix="/software", tags=["Software"])


@router_software.post("/", response_model=SoftwareResponse, status_code=status.HTTP_201_CREATED)
async def create_software_endpoint(
        software_in: SoftwareCreate,
        db: AsyncSession = Depends(get_db)
):
    """Создать новую запись о ПО"""
    return await create_software(db, software_in)

@router_software.get("/", response_model=List[SoftwareShortResponse])
async def get_software_list_endpoint(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        admin_permission: Optional[bool] = None,
        os_type: Optional[str] = None,
        db: AsyncSession = Depends(get_db)
):
    """Список ПО с фильтрацией"""
    return await get_software_list(db, skip, limit, admin_permission, os_type)

@router_software.get("/{software_id}", response_model=SoftwareResponse)
async def get_software_endpoint(software_id: int, db: AsyncSession = Depends(get_db)):
    """Получить запись о ПО по ID"""
    software = await get_software_by_id(db, software_id)
    if not software:
        raise HTTPException(status_code=404, detail="Запись о ПО не найдена")
    return software

@router_software.patch("/{software_id}", response_model=SoftwareResponse)
async def update_software_endpoint(software_id: int, software_data: SoftwareUpdate, db: AsyncSession = Depends(get_db)):
    """Обновить запись о ПО"""
    updated_software = await update_software(db, software_id, software_data)
    if not updated_software:
        raise HTTPException(status_code=404, detail="Запись о ПО не найдена")
    return updated_software

@router_software.delete("/{software_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_software_endpoint(software_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить ПО. Запрещено, если к нему привязаны активы."""

    # 1. Проверка существования
    software = await get_software_by_id(db, software_id)
    if not software:
        raise HTTPException(status_code=404, detail="Запись о ПО не найдена")

    # 2. Проверка привязок
    if await check_software_has_assets(db, software_id):
        raise HTTPException(status_code=400, detail="Невозможно удалить ПО, привязанное к активам.")

    # 3. Удаление
    await delete_software(db, software_id)
    return None

@router_software.get("/{software_id}/assets", response_model=List[AssetShortResponse])
async def get_assets_by_software_endpoint(software_id: int, db: AsyncSession = Depends(get_db)):
    """Получить все активы, на которых установлено данное ПО"""

    # Проверка существования ПО
    software = await get_software_by_id(db, software_id)
    if not software:
        raise HTTPException(status_code=404, detail="Запись о ПО не найдена")

    return await get_assets_by_software_id(db, software_id)