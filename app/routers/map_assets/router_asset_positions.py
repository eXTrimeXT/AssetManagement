from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.database.map_assets.crud_workshop import get_workshop

from app.database.map_assets.crud_asset_position import (
    get_by_asset_and_workshop, create_asset_position, get_asset_position, hard_delete_asset_position,
    get_all_asset_position_by_workshop, get_all_asset_position_by_asset, update_asset_position,
    move_asset_position, delete_asset_position
)
from app.database.map_assets.crud_asset_position import delete_all_asset_position_by_workshop

from app.schemas.map_assets.AssetPositionResponse import AssetPositionResponse
from app.schemas.map_assets.AssetPositionCreate import AssetPositionCreate
from app.schemas.map_assets.AssetPositionUpdate import AssetPositionUpdate

router_asset_positions = APIRouter(prefix="/asset-positions", tags=["asset-positions"])


@router_asset_positions.post(
    "/",
    response_model=AssetPositionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новую позицию актива",
    description="Создает новую позицию актива на карте цеха"
)
async def endpoint_create_asset_position(
        position_data: AssetPositionCreate,
        db: AsyncSession = Depends(get_db)
):
    """Создать новую позицию актива"""
    # Проверка существования цеха
    workshop = await get_workshop(db, position_data.workshop_id)
    if not workshop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Цех с ID {position_data.workshop_id} не найден"
        )

    # Проверка, нет ли уже активной позиции для этого актива в этом цехе
    existing = await get_by_asset_and_workshop(
        db, position_data.asset_id, position_data.workshop_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Актив с ID {position_data.asset_id} уже имеет активную позицию в цехе {position_data.workshop_id}"
        )

    position = await create_asset_position(db, position_data)
    return position


@router_asset_positions.get(
    "/workshop/{workshop_id}",
    response_model=List[AssetPositionResponse],
    summary="Получить все позиции в цехе",
    description="Возвращает все активные позиции активов в указанном цехе"
)
async def endpoint_get_positions_by_workshop(
        workshop_id: int,
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db)
):
    """Получить все позиции в цехе"""
    # Проверка существования цеха
    workshop = await get_workshop(db, workshop_id)
    if not workshop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Цех с ID {workshop_id} не найден"
        )

    positions = await get_all_asset_position_by_workshop(db, workshop_id, skip=skip, limit=limit)
    return positions


@router_asset_positions.get(
    "/asset/{asset_id}",
    response_model=List[AssetPositionResponse],
    summary="Получить все позиции актива",
    description="Возвращает все позиции актива (включая неактивные для истории перемещений)"
)
async def endpoint_get_positions_by_asset(
        asset_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Получить все позиции актива"""
    positions = await get_all_asset_position_by_asset(db, asset_id)
    return positions


@router_asset_positions.get(
    "/{position_id}",
    response_model=AssetPositionResponse,
    summary="Получить позицию по ID",
    description="Возвращает информацию о позиции по ее ID"
)
async def endpoint_get_asset_position(
        position_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Получить позицию по ID"""
    position = await get_asset_position(db, position_id)
    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Позиция с ID {position_id} не найдена"
        )
    return position


@router_asset_positions.put(
    "/{position_id}",
    response_model=AssetPositionResponse,
    summary="Обновить позицию",
    description="Обновляет координаты и параметры позиции"
)
async def endpoint_update_asset_position(
        position_id: int,
        position_data: AssetPositionUpdate,
        db: AsyncSession = Depends(get_db)
):
    """Обновить позицию"""
    position = await get_asset_position(db, position_id)
    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Позиция с ID {position_id} не найдена"
        )

    updated_position = await update_asset_position(db, position_id, position_data)
    return updated_position


@router_asset_positions.post(
    "/{position_id}/move",
    response_model=AssetPositionResponse,
    summary="Переместить актив на карте",
    description="Перемещает актив на новые координаты"
)
async def endpoint_move_asset_position(
        position_id: int,
        x: int,
        y: int,
        rotation: int = None,
        db: AsyncSession = Depends(get_db)
):
    """Переместить актив"""
    position = await get_asset_position(db, position_id)
    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Позиция с ID {position_id} не найдена"
        )

    if x < 0 or y < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Координаты не могут быть отрицательными"
        )

    moved_position = await move_asset_position(db, position_id, x, y, rotation)
    return moved_position


@router_asset_positions.delete(
    "/{position_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить позицию (мягкое удаление)",
    description="Помечает позицию как неактивную"
)
async def endpoint_delete_asset_position(
        position_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Мягкое удаление позиции"""
    position = await get_asset_position(db, position_id)
    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Позиция с ID {position_id} не найдена"
        )

    await delete_asset_position(db, position_id)
    return None


@router_asset_positions.delete(
    "/{position_id}/hard",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Полностью удалить позицию",
    description="Полностью удаляет позицию из базы данных (необратимо)"
)
async def endpoint_hard_delete_asset_position(
        position_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Полное удаление позиции"""
    position = await get_asset_position(db, position_id)
    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Позиция с ID {position_id} не найдена"
        )

    await hard_delete_asset_position(db, position_id)
    return None


@router_asset_positions.delete(
    "/workshop/{workshop_id}/all",
    status_code=status.HTTP_200_OK,
    summary="Удалить все позиции в цехе",
    description="Удаляет все позиции активов в указанном цехе"
)
async def endpoint_delete_all_positions_in_workshop(
        workshop_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Удалить все позиции в цехе"""
    workshop = await get_workshop(db, workshop_id)
    if not workshop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Цех с ID {workshop_id} не найден"
        )

    deleted_count = await delete_all_asset_position_by_workshop(db, workshop_id)
    return {"deleted_count": deleted_count}
