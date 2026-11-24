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

@router_asset_status.post(
    "/",
    response_model=AssetStatusResponse,
    summary="Создать статус актива / Create Asset Status",
    description=(
            "RU: Создает новый статус актива в системе. "
            "Принимает данные статуса в теле запроса и возвращает созданную запись. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Creates a new asset status in the system. "
            "Accepts status data in the request body and returns the created record. "
            "User authorization is required."
    )
)
async def create_status(status_data: AssetStatusCreate, db: AsyncSession = Depends(get_db)):
    return await create_asset_status(db, status_data)

@router_asset_status.get(
    "/",
    response_model=List[AssetStatusResponse],
    summary="Получить список статусов активов / Get Asset Statuses List",
    description=(
            "RU: Возвращает список всех статусов активов с поддержкой пагинации "
            "через параметры `skip` и `limit`. По умолчанию возвращается до 100 записей. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns a list of all asset statuses with pagination support "
            "via `skip` and `limit` parameters. By default, up to 100 records are returned. "
            "User authorization is required."
    )
)
async def read_statuses(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    return await get_asset_statuses(db, skip=skip, limit=limit)

@router_asset_status.get(
    "/{status_id}",
    response_model=AssetStatusResponse,
    summary="Получить статус актива по ID / Get Asset Status by ID",
    description=(
            "RU: Возвращает информацию о статусе актива по его уникальному идентификатору `status_id`. "
            "Если статус не найден — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns information about an asset status by its unique identifier `status_id`. "
            "If the status is not found, a 404 error is returned. "
            "User authorization is required."
    )
)
async def read_status(
        status_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    db_status = await get_asset_status(db, status_id)
    if not db_status:
        raise HTTPException(status_code=404, detail="Status not found")
    return db_status

@router_asset_status.put(
    "/{status_id}",
    response_model=AssetStatusResponse,
    summary="Обновить статус актива / Update Asset Status",
    description=(
            "RU: Полностью обновляет данные статуса актива по его `status_id`. "
            "Если статус не найден — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Fully updates the data of an asset status by its `status_id`. "
            "If the status is not found, a 404 error is returned. "
            "User authorization is required."
    )
)
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

@router_asset_status.delete(
    "/{status_id}",
    response_model=AssetStatusResponse,
    summary="Удалить статус актива / Delete Asset Status",
    description=(
            "RU: Удаляет статус актива по его `status_id`. "
            "Возвращает данные удаленной записи. Если статус не найден — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Deletes an asset status by its `status_id`. "
            "Returns the data of the deleted record. If the status is not found, a 404 error is returned. "
            "User authorization is required."
    )
)
async def delete_status(
        status_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    db_status = await delete_asset_status(db, status_id)
    if not db_status:
        raise HTTPException(status_code=404, detail="Status not found")
    return db_status