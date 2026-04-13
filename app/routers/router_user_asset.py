from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from datetime import datetime, timezone
from typing import Optional, List

from app.database.connection import get_db
from app.models.User import User
from app.models.Asset import Asset
from app.models.UserAsset import UserAsset
from app.schemas.assignments.assign import AssignmentDetailResponse, UserFullInfoResponse

router_user_assets = APIRouter(prefix="/user-assets", tags=["User-Asset Links"])

# === 1. СВЯЗАТЬ ПОЛЬЗОВАТЕЛЯ И АКТИВ ===
@router_user_assets.post("/assign", response_model=AssignmentDetailResponse, status_code=status.HTTP_201_CREATED)
async def assign_asset(
        user_id: int,
        asset_id: int,
        role: Optional[str] = "Пользователь",
        db: AsyncSession = Depends(get_db)
):
    """Связать пользователя с активом"""
    # Проверка существования
    user = await db.get(User, user_id)
    asset = await db.get(Asset, asset_id)
    if not user or not asset:
        raise HTTPException(status_code=404, detail="Пользователь или актив не найден")

    # Проверка на уже активную связь
    existing = await db.execute(
        select(UserAsset).where(
            UserAsset.user_id == user_id,
            UserAsset.asset_id == asset_id,
            UserAsset.returned_at.is_(None)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Актив уже назначен этому пользователю")

    # Создание связи
    link = UserAsset(user_id=user_id, asset_id=asset_id, role=role)
    db.add(link)
    await db.commit()
    await db.refresh(link)

    # Подгрузка актива для ответа
    await db.refresh(link, attribute_names=["asset"])
    return link


# === 2. ОТВЯЗАТЬ ПОЛЬЗОВАТЕЛЯ ОТ АКТИВА ===
@router_user_assets.post("/unassign", response_model=AssignmentDetailResponse)
async def unassign_asset(
        user_id: int,
        asset_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Отвязать пользователя от актива (фиксация возврата)"""
    result = await db.execute(
        select(UserAsset).where(
            UserAsset.user_id == user_id,
            UserAsset.asset_id == asset_id,
            UserAsset.returned_at.is_(None)
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Активная связь не найдена")

    link.returned_at = datetime.now()
    await db.commit()
    await db.refresh(link, attribute_names=["asset"])
    return link


# === 3. ПОЛНАЯ ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ + АКТИВЫ + ДЕТИ + ТИП + ПО ===
@router_user_assets.get("/user/{user_id}/full-info", response_model=UserFullInfoResponse)
async def get_user_full_info(
        user_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    Выводит всю информацию о пользователе, его активах,
    дочерних элементах активов, типах и установленном ПО.
    """
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Сложная загрузка графа связей за ОДИН эффективный запрос
    query = (
        # Выбираем пользователя
        select(User).where(User.user_id == user_id).options(
            # Загружаем назначения
            selectinload(User.assignments)
            # загружаем активы
            .selectinload(UserAsset.asset)
            # загружаем дочерние активы, типы, софт
            .options(
                selectinload(Asset.children),
                joinedload(Asset.asset_type),
                selectinload(Asset.software)
            )
        )
    )

    result = await db.execute(query)
    user_loaded = result.scalar_one_or_none()

    if not user_loaded:
        raise HTTPException(status_code=404, detail="Данные не найдены")

    return user_loaded