from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.schemas.android_data.AndroidDataSchemas import AndroidDataCreate, AndroidDataResponse
from app.database.crud_android_data import (
    create_or_update_android_data,
    get_all_android_data,
    update_android_data,
    delete_android_data
)
from app.middleware.LoggingMiddleware import logger
from app.services.auth.auth_service import require_authorized_user
from app.services.auth.permission_checker import check_permission

router_android_data = APIRouter(prefix="/android-data", tags=["android_data"])

@router_android_data.post("/", response_model=AndroidDataResponse, status_code=200)
async def endpoint_create_android_data(
        request: Request,
        data: AndroidDataCreate,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    has_perm = await check_permission(request, "android_data", "write")
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'write' на тип актива 'android_data'"
        )
    return await create_or_update_android_data(db, data)


@router_android_data.get("/", response_model=list[AndroidDataResponse])
async def endpoint_read_all_android_data(
        serial_number: Optional[str] = Query(None),
        skip: int = 0, limit: int = 100,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    return await get_all_android_data(db, serial_number, skip, limit)

@router_android_data.patch("/{serial_number}", response_model=AndroidDataResponse)
async def endpoint_update_android_data(
        request: Request,
        serial_number: str,
        data: AndroidDataCreate,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    has_perm = await check_permission(request, "android_data", "write")
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'write' на тип актива 'android_data'"
        )

    db_record = await update_android_data(db, serial_number, data)
    if db_record is None:
        logger.warning("Данные Android не найдены")
        raise HTTPException(status_code=404, detail="Данные Android не найдены")
    return db_record

@router_android_data.delete("/{serial_number}", status_code=200)
async def endpoint_delete_android_data(
        request: Request,
        serial_number: str,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    has_perm = await check_permission(request, "android_data", "write")
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'write' на тип актива 'android_data'"
        )

    db_record = await delete_android_data(db, serial_number)
    if db_record is None:
        logger.warning("Данные Android не найдены")
        raise HTTPException(status_code=404, detail="Данные Android не найдены")
    return None