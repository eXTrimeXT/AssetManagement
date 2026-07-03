from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.schemas.pc_data.pc_data_schemas import PCDataCreate, PCDataResponse
from app.database.crud_pc_data import create_or_update_pc_data, get_all_pc_data, update_pc_data, delete_pc_data
from app.middleware.LoggingMiddleware import logger
# from app.services.auth.auth_service import require_authorized_user
# from app.services.permissions.permissions_rules import has_pc_data_sender_permission
# from app.models.User import User

router_pc_data = APIRouter(prefix="/pc-data", tags=["pc_data"])

@router_pc_data.post("/", response_model=PCDataResponse, status_code=200)
async def endpoint_create_pc_data(
        pc_data: PCDataCreate,
        db: AsyncSession = Depends(get_db),
        # current_user: User = Depends(require_authorized_user)
):
    # if not has_pc_data_sender_permission(current_user):
    #     raise HTTPException(status_code=403, detail="Доступ запрещен!")
    return await create_or_update_pc_data(db, pc_data)

@router_pc_data.get("/", response_model=list[PCDataResponse])
async def endpoint_read_all_pc_data(
        username: Optional[str] = Query(None),
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db),
):
    return await get_all_pc_data(db, username, skip, limit)

@router_pc_data.patch("/{username}", response_model=PCDataResponse)
async def endpoint_update_pc_data(
        username: str,
        pc_data: PCDataCreate,
        db: AsyncSession = Depends(get_db),
        # current_user: User = Depends(require_authorized_user)
):
    # if not has_pc_data_sender_permission(current_user):
    #     raise HTTPException(status_code=403, detail="Доступ запрещен!")

    db_pc = await update_pc_data(db, username, pc_data)
    if db_pc is None:
        logger.warning("Данные о ПК не найдены")
        raise HTTPException(status_code=404, detail="Данные о ПК не найдены")
    return db_pc

@router_pc_data.delete("/{username}", status_code=200)
async def endpoint_delete_pc_data(
        username: str,
        db: AsyncSession = Depends(get_db),
        # current_user: User = Depends(require_authorized_user)
):
    # if not has_pc_data_sender_permission(current_user):
    #     raise HTTPException(status_code=403, detail="Доступ запрещен!")

    db_pc = await delete_pc_data(db, username)
    if db_pc is None:
        logger.warning("Данные о ПК не найдены")
        raise HTTPException(status_code=404, detail="Данные о ПК не найдены")
    return None