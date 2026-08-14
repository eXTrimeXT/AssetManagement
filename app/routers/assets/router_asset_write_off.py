from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.database.connection import get_db
from app.database.assets.crud_asset_write_off import (
    create_write_off,
    get_write_offs_list,
    get_write_off_by_id,
    delete_write_off
)
from app.schemas.assets.AssetWriteOffSchemas import AssetWriteOffCreate, AssetWriteOffResponse
from app.services.auth.auth_service import extract_login_from_request, require_authorized_user

router_asset_write_off = APIRouter(
    prefix="/write-off",
    tags=["Asset Write-Off"]
)


@router_asset_write_off.post("/", response_model=AssetWriteOffResponse)
async def create_write_off_endpoint(
        data: AssetWriteOffCreate,
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Создать акт списания актива"""
    # user_info = await extract_login_from_request(request)
    # employee_id = user_info.get("login") or "unknown"

    write_off = await create_write_off(db, data, current_user.employee_id)
    if not write_off:
        raise HTTPException(status_code=404, detail="Asset not found")
    return write_off


@router_asset_write_off.get("/", response_model=List[AssetWriteOffResponse])
async def list_write_offs(
        skip: int = 0,
        limit: int = 100,
        asset_id: Optional[int] = None,
        db: AsyncSession = Depends(get_db)
):
    """Получить список актов списания"""
    return await get_write_offs_list(db, skip=skip, limit=limit, asset_id=asset_id)


@router_asset_write_off.get("/{write_off_id}", response_model=AssetWriteOffResponse)
async def get_write_off(write_off_id: int, db: AsyncSession = Depends(get_db)):
    """Получить детали акта списания"""
    write_off = await get_write_off_by_id(db, write_off_id)
    if not write_off:
        raise HTTPException(status_code=404, detail="Write-off record not found")
    return write_off


@router_asset_write_off.delete("/{write_off_id}")
async def remove_write_off(write_off_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить акт списания"""
    success = await delete_write_off(db, write_off_id)
    if not success:
        raise HTTPException(status_code=404, detail="Write-off record not found")
    return {"status": "deleted"}