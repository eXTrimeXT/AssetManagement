from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.services.auth.auth_service import require_authorized_user
from app.services.sap.sync_sap_assets import (
    sync_sap_assets,
    get_sap_departments,
    get_sap_asset_classes,
    sync_sap_departments,
    sync_sap_material_classes
)

router_from_sap = APIRouter(prefix="/sap", tags=["SAP API [READ ONLY]"])

@router_from_sap.get(
    "/departments",
    summary="Получить список подразделений из SAP API"
)
async def get_sap_departments_endpoint(
        limit: int = Query(default=1000, description="Лимит записей"),
        offset: int = Query(default=0, description="Смещение (offset)"),
        department: Optional[str] = Query(None, description="Аббревиатура департамента"),
        department_name_like: Optional[str] = Query(None, description="Поиск по названию департамента"),
        current_user=Depends(require_authorized_user)
):
    """
    Прокси-запрос к внешнему SAP API для получения подразделений.
    """
    return await get_sap_departments(
        limit=limit,
        offset=offset,
        department=department,
        department_name_like=department_name_like
    )


@router_from_sap.get(
    "/asset-classes",
    summary="Получить список классов активов из SAP API"
)
async def get_sap_asset_classes_endpoint(
        limit: int = Query(default=200, description="Лимит записей"),
        offset: int = Query(default=0, description="Смещение (offset)"),
        language: str = Query(default="R", description="Код языка"),
        current_user=Depends(require_authorized_user)
):
    """
    Прокси-запрос к внешнему SAP API для получения классов активов.
    """
    return await get_sap_asset_classes(
        limit=limit,
        offset=offset,
        language=language
    )


@router_from_sap.post("/sync-assets-from-sap")
async def sync_assets_from_sap(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    result = await sync_sap_assets(db)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message"))

    return result

@router_from_sap.post("/sync-departments", summary="Синхронизировать справочник подразделений (MVZ) в БД")
async def sync_departments_to_db_endpoint(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Загружает актуальный список подразделений из SAP API и сохраняет/обновляет
    их в локальной таблице sap_departments (использует UPSERT).
    """
    result = await sync_sap_departments(db)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message"))

    return result


@router_from_sap.post("/sync-material-classes", summary="Синхронизировать справочник классов материалов в БД")
async def sync_material_classes_to_db_endpoint(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """
    Загружает актуальный список классов материалов из SAP API и сохраняет/обновляет
    их в локальной таблице sap_material_classes (использует UPSERT).
    """
    result = await sync_sap_material_classes(db)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message"))

    return result