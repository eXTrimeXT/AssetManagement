from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.schemas.pc_data.PcDataSchemas import PCDataCreate, PCDataResponse
from app.database.crud_pc_data import create_or_update_pc_data, get_all_pc_data, update_pc_data, delete_pc_data
from app.middleware.LoggingMiddleware import logger
from app.services.auth.auth_service import require_authorized_user
from app.services.auth.permission_checker import check_permission

router_pc_data = APIRouter(prefix="/pc-data", tags=["PC Data"])

@router_pc_data.post(
    "/",
    response_model=PCDataResponse,
    status_code=200,
    summary="Создать или обновить данные ПК / Create or Update PC Data",
    description=(
            "RU: Создает новую запись данных о ПК или обновляет существующую (upsert). "
            "Данные передаются в теле запроса. Проверяет наличие права на запись (`write`) "
            "для ресурса `pc_data`. При отсутствии прав возвращается ошибка 403. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Creates a new PC data record or updates an existing one (upsert). "
            "Data is passed in the request body. Checks for write permission (`write`) "
            "on the `pc_data` resource. A 403 error is returned if permissions are missing. "
            "User authorization is required."
    )
)
async def endpoint_create_pc_data(
        request: Request,
        pc_data: PCDataCreate,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    has_perm = await check_permission(request, "pc_data", "write")
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'write' на тип актива 'pc_data'"
        )
    return await create_or_update_pc_data(db, pc_data)


@router_pc_data.get(
    "/",
    response_model=list[PCDataResponse],
    summary="Получить список данных о ПК / Get PC Data List",
    description=(
            "RU: Возвращает список записей данных о ПК с поддержкой пагинации "
            "(`skip`, `limit`) и фильтрации по имени пользователя (`username`). "
            "По умолчанию возвращается до 100 записей. "
            "Требуется право на чтение (`read`) для ресурса `computer` или `pc_data` — "
            "при отсутствии обоих прав возвращается ошибка 403. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns a list of PC data records with pagination support "
            "(`skip`, `limit`) and filtering by username (`username`). "
            "By default, up to 100 records are returned. "
            "Requires read permission (`read`) on the `computer` or `pc_data` resource — "
            "a 403 error is returned if neither permission is present. "
            "User authorization is required."
    )
)
async def endpoint_read_all_pc_data(
        request: Request,
        username: Optional[str] = Query(None),
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    has_perm = await check_permission(request, "computer", "read")
    has_system_perm = await check_permission(request, "pc_data", "read")

    if not has_perm and not has_system_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'read' на тип актива 'computer'"
        )
    return await get_all_pc_data(db, username, skip, limit)


@router_pc_data.patch(
    "/{username}",
    response_model=PCDataResponse,
    summary="Обновить данные ПК по имени пользователя / Update PC Data by Username",
    description=(
            "RU: Обновляет существующую запись данных о ПК по имени пользователя `username`. "
            "Проверяет наличие права на запись (`write`) для ресурса `pc_data`. "
            "Если запись не найдена — возвращается ошибка 404, при отсутствии прав — 403. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Updates an existing PC data record by the username `username`. "
            "Checks for write permission (`write`) on the `pc_data` resource. "
            "If the record is not found, a 404 error is returned; if permissions are missing, a 403 error is returned. "
            "User authorization is required."
    )
)
async def endpoint_update_pc_data(
        request: Request,
        username: str,
        pc_data: PCDataCreate,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    has_perm = await check_permission(request, "pc_data", "write")
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'write' на тип актива 'pc_data'"
        )

    db_pc = await update_pc_data(db, username, pc_data)
    if db_pc is None:
        logger.warning("Данные о ПК не найдены")
        raise HTTPException(status_code=404, detail="Данные о ПК не найдены")
    return db_pc


@router_pc_data.delete(
    "/{username}",
    status_code=200,
    summary="Удалить данные ПК по имени пользователя / Delete PC Data by Username",
    description=(
            "RU: Удаляет запись данных о ПК по имени пользователя `username`. "
            "Проверяет наличие права на запись (`write`) для ресурса `pc_data`. "
            "Если запись не найдена — возвращается ошибка 404, при отсутствии прав — 403. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Deletes a PC data record by the username `username`. "
            "Checks for write permission (`write`) on the `pc_data` resource. "
            "If the record is not found, a 404 error is returned; if permissions are missing, a 403 error is returned. "
            "User authorization is required."
    )
)
async def endpoint_delete_pc_data(
        request: Request,
        username: str,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    has_perm = await check_permission(request, "pc_data", "write")
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'write' на тип актива 'pc_data'"
        )

    db_pc = await delete_pc_data(db, username)
    if db_pc is None:
        logger.warning("Данные о ПК не найдены")
        raise HTTPException(status_code=404, detail="Данные о ПК не найдены")
    return None