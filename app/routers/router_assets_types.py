import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database.connection import get_db
from app.database.asset_types.crud_asset_types import (
    create_asset_type,
    get_asset_type_by_type_id,
    list_asset_types,
    update_asset_type,
    delete_asset_type
)
from app.schemas.asset_types.AssetTypeCreate import AssetTypeCreate
from app.schemas.asset_types.AssetTypeResponse import AssetTypeResponse
from app.schemas.asset_types.AssetTypeUpdate import AssetTypeUpdate

# Инициализируем логгер
logger = structlog.get_logger()

router_assets_types = APIRouter(prefix="/assets-types", tags=["assets-types"])

@router_assets_types.post("/", response_model=AssetTypeResponse, status_code=status.HTTP_201_CREATED)
async def create(data: AssetTypeCreate, db: AsyncSession = Depends(get_db)):
    log = logger.bind(action="create_asset_type", type_id=data.type_id)

    try:
        existing = await get_asset_type_by_type_id(db, data.type_id)
        if existing:
            log.warning("duplicate_type_id", detail="Type ID already exists")
            raise HTTPException(status_code=400, detail="Type ID already exists")

        new_obj = await create_asset_type(db, data)
        log.info("success", name=data.name, asset_type_id=new_obj.asset_type_id)
        return new_obj

    except HTTPException:
        raise
    except IntegrityError as e:
        log.error("db_integrity_error", error=str(e.orig), exc_info=True)
        raise HTTPException(status_code=400, detail="Database constraint violation")
    except SQLAlchemyError as e:
        log.error("db_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal database error")

@router_assets_types.get("/{type_id}", response_model=AssetTypeResponse)
async def get(type_id: int, db: AsyncSession = Depends(get_db)):
    log = logger.bind(action="get_asset_type", type_id=type_id)

    try:
        obj = await get_asset_type_by_type_id(db, type_id)
        if not obj:
            log.warning("not_found")
            raise HTTPException(status_code=404, detail="Asset Type not found")

        log.debug("retrieved", name=obj.name)
        return obj

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        log.error("db_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal database error")

@router_assets_types.get("/", response_model=list[AssetTypeResponse])
async def list_all(db: AsyncSession = Depends(get_db)):
    log = logger.bind(action="list_asset_types")

    try:
        items = await list_asset_types(db)
        log.info("success", count=len(items))
        return items

    except SQLAlchemyError as e:
        log.error("db_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal database error")

@router_assets_types.patch("/{type_id}", response_model=AssetTypeResponse)
async def patch(type_id: int, data: AssetTypeUpdate, db: AsyncSession = Depends(get_db)):
    log = logger.bind(action="update_asset_type", type_id=type_id)

    try:
        obj = await get_asset_type_by_type_id(db, type_id)
        if not obj:
            log.warning("not_found")
            raise HTTPException(status_code=404, detail="Asset Type not found")

        updated_fields = list(data.model_dump(exclude_unset=True).keys())
        updated_obj = await update_asset_type(db, obj, data)

        log.info("success", updated_fields=updated_fields)
        return updated_obj

    except HTTPException:
        raise
    except IntegrityError as e:
        log.error("db_integrity_error", error=str(e.orig), exc_info=True)
        raise HTTPException(status_code=400, detail="Database constraint violation")
    except SQLAlchemyError as e:
        log.error("db_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal database error")

@router_assets_types.delete("/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(type_id: int, db: AsyncSession = Depends(get_db)):
    log = logger.bind(action="delete_asset_type", type_id=type_id)

    try:
        obj = await get_asset_type_by_type_id(db, type_id)
        if not obj:
            log.warning("not_found")
            raise HTTPException(status_code=404, detail="Asset Type not found")

        await delete_asset_type(db, obj)
        log.info("success", deleted_name=obj.name)

    except HTTPException:
        raise
    except IntegrityError as e:
        # Например, если на тип ссылаются активы и FK не позволяет удалить
        log.error("db_integrity_error", error=str(e.orig), exc_info=True)
        raise HTTPException(status_code=400, detail="Cannot delete: referenced by existing assets")
    except SQLAlchemyError as e:
        log.error("db_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal database error")