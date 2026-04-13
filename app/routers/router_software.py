# from fastapi import APIRouter, Depends, HTTPException, status, Query
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select
# from sqlalchemy.orm import selectinload
# from typing import List, Optional, Any
#
# from app.database.connection import get_db
# from app.models.Software import Software
# from app.models.Asset import Asset
# from app.schemas.software.SoftwareCreate import SoftwareCreate
# from app.schemas.software.SoftwareUpdate import SoftwareUpdate
# from app.schemas.software.SoftwareResponse import SoftwareResponse, SoftwareShortResponse


from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional, Any

from app.database.connection import get_db
from app.models.Software import Software
from app.models.Asset import Asset
from app.schemas.software.SoftwareCreate import SoftwareCreate
from app.schemas.software.SoftwareUpdate import SoftwareUpdate
from app.schemas.software.SoftwareResponse import SoftwareResponse, SoftwareShortResponse
from app.schemas.assets.AssetResponse import AssetShortResponse

router_software = APIRouter(prefix="/software", tags=["Software"])

async def _get_software(software_id: int, db: AsyncSession) -> Any | None:
    result = await db.execute(select(Software).where(Software.software_id == software_id))
    software = result.scalar_one_or_none()
    if not software:
        raise HTTPException(status_code=404, detail="Запись о ПО не найдена")
    return software

@router_software.post("/", response_model=SoftwareResponse, status_code=status.HTTP_201_CREATED)
async def create_software(software_in: SoftwareCreate, db: AsyncSession = Depends(get_db)):
    """Создать новую запись о ПО (независимо от активов)"""
    db_software = Software(**software_in.model_dump())
    db.add(db_software)
    await db.commit()
    await db.refresh(db_software)
    return db_software

@router_software.get("/", response_model=List[SoftwareShortResponse])
async def get_software_list(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        admin_permission: Optional[bool] = None,
        os_type: Optional[str] = None,
        db: AsyncSession = Depends(get_db)
):
    """Список ПО с фильтрацией"""
    query = select(Software)
    if admin_permission is not None:
        query = query.where(Software.admin_permission == admin_permission)
    if os_type:
        query = query.where(Software.os_type.ilike(f"%{os_type}%"))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router_software.get("/{software_id}", response_model=SoftwareResponse)
async def get_software(software_id: int, db: AsyncSession = Depends(get_db)):
    return await _get_software(software_id, db)

@router_software.patch("/{software_id}", response_model=SoftwareResponse)
async def update_software(software_id: int, software_data: SoftwareUpdate, db: AsyncSession = Depends(get_db)):
    """Обновить запись о ПО"""
    software = await _get_software(software_id, db)
    update_data = software_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(software, key, value)
    await db.commit()
    await db.refresh(software)
    return software

@router_software.delete("/{software_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_software(software_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить ПО. Запрещено, если к нему привязаны активы."""
    software = await _get_software(software_id, db)
    # Проверка привязок
    linked = await db.execute(select(Asset).where(Asset.software_id == software_id).limit(1))
    if linked.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Невозможно удалить ПО, привязанное к активам.")

    await db.delete(software)
    await db.commit()
    return None

@router_software.get("/{software_id}/assets", response_model=List[AssetShortResponse])
async def get_assets_by_software(software_id: int, db: AsyncSession = Depends(get_db)):
    """Получить все активы, на которых установлено данное ПО"""
    await _get_software(software_id, db) # Проверка существования
    result = await db.execute(
        select(Asset)
        .where(Asset.software_id == software_id)
        .where(Asset.deleted_at.is_(None))
    )
    return result.scalars().all()