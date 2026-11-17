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
    summary="Получить список подразделений из SAP API / Get Departments List from SAP API",
    description=(
            "RU: Прокси-запрос к внешнему SAP API для получения списка подразделений (MVZ). "
            "Поддерживает пагинацию через параметры `limit` и `offset`, "
            "фильтрацию по аббревиатуре департамента (`department`) и поиск по названию (`department_name_like`). "
            "Данные возвращаются напрямую из SAP без кеширования на стороне сервера. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Proxy request to the external SAP API to retrieve the list of departments (MVZ). "
            "Supports pagination via `limit` and `offset` parameters, "
            "filtering by department abbreviation (`department`), and search by name (`department_name_like`). "
            "Data is returned directly from SAP without server-side caching. "
            "User authorization is required."
    )
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
    summary="Получить список классов активов из SAP API / Get Asset Classes List from SAP API",
    description=(
            "RU: Прокси-запрос к внешнему SAP API для получения списка классов активов. "
            "Поддерживает пагинацию через параметры `limit` и `offset`, "
            "а также параметр `language` для указания кода языка (по умолчанию `R`). "
            "Данные возвращаются напрямую из SAP без кеширования на стороне сервера. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Proxy request to the external SAP API to retrieve the list of asset classes. "
            "Supports pagination via `limit` and `offset` parameters, "
            "as well as the `language` parameter to specify the language code (default is `R`). "
            "Data is returned directly from SAP without server-side caching. "
            "User authorization is required."
    )
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


@router_from_sap.post(
    "/sync-assets-from-sap",
    summary="Синхронизировать активы из SAP / Sync Assets from SAP",
    description=(
            "RU: Запускает процесс синхронизации активов из внешнего SAP API в локальную базу данных. "
            "Загружает актуальные данные активов из SAP и обновляет локальное хранилище. "
            "В случае ошибки синхронизации возвращается HTTP 500 с описанием проблемы. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Triggers the synchronization process of assets from the external SAP API to the local database. "
            "Loads the latest asset data from SAP and updates the local storage. "
            "In case of a synchronization error, HTTP 500 is returned with a description of the issue. "
            "User authorization is required."
    )
)
async def sync_assets_from_sap(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    result = await sync_sap_assets(db)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message"))

    return result


@router_from_sap.post(
    "/sync-departments",
    summary="Синхронизировать справочник подразделений (MVZ) в БД / Sync Departments Directory (MVZ) to DB",
    description=(
            "RU: Загружает актуальный список подразделений из SAP API и сохраняет/обновляет "
            "их в локальной таблице `sap_departments`, используя операцию UPSERT. "
            "В случае ошибки синхронизации возвращается HTTP 500 с описанием проблемы. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Loads the latest list of departments from the SAP API and saves/updates "
            "them in the local `sap_departments` table using an UPSERT operation. "
            "In case of a synchronization error, HTTP 500 is returned with a description of the issue. "
            "User authorization is required."
    )
)
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


@router_from_sap.post(
    "/sync-material-classes",
    summary="Синхронизировать справочник классов материалов в БД / Sync Material Classes Directory to DB",
    description=(
            "RU: Загружает актуальный список классов материалов из SAP API и сохраняет/обновляет "
            "их в локальной таблице `sap_material_classes`, используя операцию UPSERT. "
            "В случае ошибки синхронизации возвращается HTTP 500 с описанием проблемы. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Loads the latest list of material classes from the SAP API and saves/updates "
            "them in the local `sap_material_classes` table using an UPSERT operation. "
            "In case of a synchronization error, HTTP 500 is returned with a description of the issue. "
            "User authorization is required."
    )
)
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