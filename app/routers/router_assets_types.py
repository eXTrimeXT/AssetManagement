import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.database.connection import get_db
from app.database.crud_asset_types import (
    create_asset_type, list_asset_types, update_asset_type,
    delete_asset_type, get_asset_type_by_id, get_asset_type_by_en_name
)
from app.schemas.asset_types.AssetTypesSchemas import AssetTypeCreate, AssetTypeResponse, AssetTypeUpdate
from app.service.auth.auth_service import require_authorized_user
from app.service.permissions.permissions_rules import has_read_permission, has_write_permission

logger = logging.getLogger(__name__)

router_assets_types = APIRouter(
    prefix="/assets-types",
    tags=["Assets Types"],
    dependencies=[Depends(require_authorized_user)]
)

@router_assets_types.post("/", response_model=AssetTypeResponse, status_code=status.HTTP_201_CREATED)
async def create(
        data: AssetTypeCreate,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    if not has_write_permission(current_user, data.en_name):
        logger.warning(f"Доступ на запись к ресурсу типа '{data.en_name}' не разрешен")
        raise HTTPException(status_code=403, detail=f"Доступ на запись к ресурсу типа '{data.en_name}' не разрешен")

    try:
        new_obj = await create_asset_type(db, data)
        logger.info("Тип создан")
        return new_obj
    except IntegrityError as e:
        logger.error("Нарушение ограничений базы данных")
        raise HTTPException(status_code=400, detail="Нарушение ограничений базы данных")
    except Exception as e:
        logger.error(f"Ошибка {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router_assets_types.get("/", response_model=List[AssetTypeResponse])
async def list_all(db: AsyncSession = Depends(get_db), current_user = Depends(require_authorized_user)):
    items = await list_asset_types(db)
    for item in items:
        if not has_read_permission(current_user, item.en_name):
            logger.warning("Нет доступа для чтения")
            raise HTTPException(403, "Нет доступа для чтения")
    return items

@router_assets_types.get("/id/{asset_type_id}", response_model=AssetTypeResponse)
async def get_by_id(asset_type_id: int, db: AsyncSession = Depends(get_db), current_user = Depends(require_authorized_user)):
    obj = await get_asset_type_by_id(db, asset_type_id)
    if not obj:
        logger.warning("Тип актива не найден")
        raise HTTPException(404, "Тип актива не найден")
    if not has_read_permission(current_user, obj.en_name):
        logger.warning("Нет доступа для чтения")
        raise HTTPException(403, "Нет доступа для чтения")
    return obj

@router_assets_types.get("/en_name/{en_name}", response_model=AssetTypeResponse)
async def get_by_en_name(en_name: str, db: AsyncSession = Depends(get_db), current_user = Depends(require_authorized_user)):
    obj = await get_asset_type_by_en_name(db, en_name)
    if not obj:
        logger.warning("Тип актива не найден")
        raise HTTPException(404, "Тип актива не найден")
    if not has_read_permission(current_user, obj.en_name):
        logger.warning("Нет доступа для чтения")
        raise HTTPException(403, "Нет доступа для чтения")
    return obj

@router_assets_types.patch("/{asset_type_id}", response_model=AssetTypeResponse)
async def patch(asset_type_id: int, data: AssetTypeUpdate, db: AsyncSession = Depends(get_db), current_user = Depends(require_authorized_user)):
    obj = await get_asset_type_by_id(db, asset_type_id)
    if not obj:
        logger.warning("Тип актива не найден")
        raise HTTPException(404, "Тип актива не найден")
    if not has_write_permission(current_user, obj.en_name):
        logger.warning("Нет доступа для записи")
        raise HTTPException(403, "Нет доступа для записи")
    return await update_asset_type(db, obj, data)

@router_assets_types.delete("/{asset_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(asset_type_id: int, db: AsyncSession = Depends(get_db), current_user = Depends(require_authorized_user)):
    obj = await get_asset_type_by_id(db, asset_type_id)
    if not obj:
        logger.warning("Тип актива не найден")
        raise HTTPException(404, "Тип актива не найден")
    if not has_write_permission(current_user, obj.en_name):
        logger.warning("Нет доступа для записи")
        raise HTTPException(403, "Нет доступа для записи")
    await delete_asset_type(db, obj)