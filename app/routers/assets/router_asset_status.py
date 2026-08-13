from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.database.connection import get_db
from app.database.assets.crud_asset_status import (
    create_asset_status,
    get_asset_statuses,
    get_asset_status,
    update_asset_status,
    delete_asset_status
)
from app.schemas.assets.AssetStatusSchemas import AssetStatusCreate, AssetStatusUpdate, AssetStatusResponse
from app.services.auth.auth_service import require_authorized_user

router_asset_status = APIRouter(prefix="/asset-status", tags=["Asset Status"])

@router_asset_status.post("/", response_model=AssetStatusResponse)
async def create_status(status_data: AssetStatusCreate, db: AsyncSession = Depends(get_db)):
    return await create_asset_status(db, status_data)

@router_asset_status.get("/", response_model=List[AssetStatusResponse])
async def read_statuses(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    return await get_asset_statuses(db, skip=skip, limit=limit)

@router_asset_status.get("/{status_id}", response_model=AssetStatusResponse)
async def read_status(
        status_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    db_status = await get_asset_status(db, status_id)
    if not db_status:
        raise HTTPException(status_code=404, detail="Status not found")
    return db_status

@router_asset_status.put("/{status_id}", response_model=AssetStatusResponse)
async def update_status(
        status_id: int,
        status_data: AssetStatusUpdate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    db_status = await update_asset_status(db, status_id, status_data)
    if not db_status:
        raise HTTPException(status_code=404, detail="Status not found")
    return db_status

@router_asset_status.delete("/{status_id}", response_model=AssetStatusResponse)
async def delete_status(
        status_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    db_status = await delete_asset_status(db, status_id)
    if not db_status:
        raise HTTPException(status_code=404, detail="Status not found")
    return db_status