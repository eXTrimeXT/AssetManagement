from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.schemas.Assignment import AssignmentDetailResponse, UserFullInfoResponse

# Импорт CRUD функций
from app.database.user_assets.crud_user_assets import (
    get_user_by_id,
    get_asset_by_id,
    check_active_assignment_exists,
    create_assignment,
    unassign_asset,
    get_user_full_info
)

router_user_assets = APIRouter(prefix="/user-assets", tags=["User-Asset Links"])

@router_user_assets.post("/assign", response_model=AssignmentDetailResponse, status_code=status.HTTP_201_CREATED)
async def assign_asset_endpoint(user_id: int, asset_id: int, db: AsyncSession = Depends(get_db)):
    """Связать пользователя с активом"""

    # 1. Проверка существования пользователя и актива
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    asset = await get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")

    # 2. Проверка на дубликат активной связи
    if await check_active_assignment_exists(db, user_id, asset_id):
        raise HTTPException(status_code=400, detail="Актив уже назначен этому пользователю")

    # 3. Создание связи
    return await create_assignment(db, user_id, asset_id)

@router_user_assets.post("/unassign", response_model=AssignmentDetailResponse)
async def unassign_asset_endpoint(user_id: int, asset_id: int, db: AsyncSession = Depends(get_db)):
    """Отвязать пользователя от актива (фиксация возврата)"""

    link = await unassign_asset(db, user_id, asset_id)

    if not link:
        raise HTTPException(status_code=404, detail="Активная связь не найдена")

    return link

@router_user_assets.get("/user/{user_id}/full-info", response_model=UserFullInfoResponse)
async def get_user_full_info_endpoint(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Выводит всю информацию о пользователе, его активах,
    дочерних элементах активов, типах и установленном ПО.
    """

    # 1. Проверка существования пользователя (опционально, т.к. get_user_full_info вернет None)
    user_exists = await get_user_by_id(db, user_id)
    if not user_exists:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # 2. Получение полной информации
    user_loaded = await get_user_full_info(db, user_id)

    if not user_loaded:
        raise HTTPException(status_code=404, detail="Данные не найдены")

    return user_loaded