from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.schemas.android_data.android_data_schemas import AndroidDataCreate, AndroidDataResponse
from app.database.crud_android_data import (
    create_or_update_android_data,
    get_all_android_data,
    update_android_data,
    delete_android_data
)
# from app.services.permissions.permissions_rules import has_android_sender_permission
# from app.services.auth.auth_service import require_authorized_user
# from app.models.User import User
from app.middleware.LoggingMiddleware import logger

router_android_data = APIRouter(prefix="/android-data", tags=["android_data"])

@router_android_data.post("/", response_model=AndroidDataResponse, status_code=200)
async def endpoint_create_android_data(
        data: AndroidDataCreate,
        db: AsyncSession = Depends(get_db),
        # current_user: User = Depends(require_authorized_user)
):
    # if not has_android_sender_permission(current_user):
    #     raise HTTPException(status_code=403, detail="Доступ запрещен!")
    return await create_or_update_android_data(db, data)


@router_android_data.get("/", response_model=list[AndroidDataResponse])
async def endpoint_read_all_android_data(
        serial_number: Optional[str] = Query(None),
        skip: int = 0, limit: int = 100,
        db: AsyncSession = Depends(get_db)
):
    return await get_all_android_data(db, serial_number, skip, limit)

@router_android_data.patch("/{serial_number}", response_model=AndroidDataResponse)
async def endpoint_update_android_data(
        serial_number: str,
        data: AndroidDataCreate,
        db: AsyncSession = Depends(get_db),
        # current_user: User = Depends(require_authorized_user)
):
    # if not has_android_sender_permission(current_user):
    #     raise HTTPException(status_code=403, detail="Доступ запрещен!")

    db_record = await update_android_data(db, serial_number, data)
    if db_record is None:
        logger.warning("Данные Android не найдены")
        raise HTTPException(status_code=404, detail="Данные Android не найдены")
    return db_record

@router_android_data.delete("/{serial_number}", status_code=200)
async def endpoint_delete_android_data(
        serial_number: str,
        db: AsyncSession = Depends(get_db),
        # current_user: User = Depends(require_authorized_user)
):
    # if not has_android_sender_permission(current_user):
    #     raise HTTPException(status_code=403, detail="Доступ запрещен!")

    db_record = await delete_android_data(db, serial_number)
    if db_record is None:
        logger.warning("Данные Android не найдены")
        raise HTTPException(status_code=404, detail="Данные Android не найдены")
    return None