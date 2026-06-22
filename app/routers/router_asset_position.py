from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.database import crud_asset_position, crud_assets
from app.schemas.asset_position.AssetPosition import (
    AssetPositionCreate,
    AssetPositionUpdate,
    AssetPositionMove,
    AssetPositionResponse,
)

router_asset_position = APIRouter(prefix="/asset-positions", tags=["Asset Positions"])


@router_asset_position.post("/", response_model=AssetPositionResponse, status_code=201)
async def create_asset_position(
        data: AssetPositionCreate,
        db: AsyncSession = Depends(get_db)
):
    """
    Создание позиции актива на карте цеха.
    Если у актива уже есть активная позиция, она будет деактивирована.
    """
    try:
        position = await crud_asset_position.create_position(db, data)
        return position
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router_asset_position.get("/", response_model=List[AssetPositionResponse])
async def get_all_asset_positions(
        skip: int = Query(0, ge=0, description="Пропуск записей"),
        limit: int = Query(100, ge=1, le=1000, description="Лимит записей"),
        db: AsyncSession = Depends(get_db)
):
    """
    Получение списка всех активных позиций всех активов.
    Возвращает позиции с данными активов и цехов.
    """
    positions_data = await crud_asset_position.get_all_positions_with_assets(
        db, skip=skip, limit=limit
    )

    result = []
    for pos_data in positions_data:
        position = pos_data[0]
        asset_name = pos_data[1]
        asset_inventory_id = pos_data[2]
        asset_serial_number = pos_data[3]
        workshop_name = pos_data[4]
        workshop_code = pos_data[5]

        # Определяем тип актива через цепочку model -> class -> type
        asset_type = None
        if position.asset and position.asset.model:
            if position.asset.model.asset_class and position.asset.model.asset_class.asset_type:
                asset_type = position.asset.model.asset_class.asset_type.en_name

        result.append(AssetPositionResponse(
            id=position.id,
            asset_id=position.asset_id,
            workshop_id=position.workshop_id,
            x=position.x,
            y=position.y,
            rotation=position.rotation,
            scale=position.scale,
            is_active=position.is_active,
            created_at=position.created_at,
            updated_at=position.updated_at,
            asset_name=asset_name,
            asset_inventory_id=asset_inventory_id,
            asset_serial_number=asset_serial_number,
            asset_type=asset_type
        ))

    return result


@router_asset_position.get("/workshop/{workshop_id}", response_model=List[AssetPositionResponse])
async def get_positions_by_workshop(
        workshop_id: int,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        db: AsyncSession = Depends(get_db)
):
    """
    Получение всех активных позиций активов для конкретного цеха.
    """
    positions = await crud_asset_position.get_positions_by_workshop(
        db, workshop_id, skip=skip, limit=limit
    )
    return positions


@router_asset_position.get("/{position_id}", response_model=AssetPositionResponse)
async def get_position(
        position_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    Получение позиции по ID.
    """
    position = await crud_asset_position.get_position(db, position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    return position


@router_asset_position.patch("/id/{position_id}", response_model=AssetPositionResponse)
async def update_asset_position(
        position_id: int,
        data: AssetPositionUpdate,
        db: AsyncSession = Depends(get_db)
):
    """
    Обновление позиции актива (перемещение, поворот, масштаб).
    """
    try:
        position = await crud_asset_position.update_position(db, position_id, data)
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
        return position
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router_asset_position.delete("/{position_id}", status_code=204)
async def delete_asset_position(
        position_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    Удаление позиции актива с карты.
    """
    success = await crud_asset_position.delete_position(db, position_id)
    if not success:
        raise HTTPException(status_code=404, detail="Position not found")
    return None


# === Эндпоинты для быстрого перемещения активов ===
@router_asset_position.post("/asset/{asset_id}/move", response_model=AssetPositionResponse)
async def move_asset(
        asset_id: int,
        data: AssetPositionMove,
        workshop_id: int = Query(..., description="ID цеха"),
        db: AsyncSession = Depends(get_db)
):
    """
    Быстрое перемещение актива на карте (только координаты X, Y).
    Если позиции не существует — создаст новую.
    """
    # Проверяем, есть ли уже активная позиция
    existing_position = await crud_assets.get_active_asset_position(db, asset_id)

    if existing_position:
        # Обновляем существующую
        update_data = AssetPositionUpdate(x=data.x, y=data.y)
        position = await crud_asset_position.update_position(
            db, existing_position.id, update_data
        )
    else:
        # Создаем новую
        create_data = AssetPositionCreate(
            asset_id=asset_id,
            workshop_id=workshop_id,
            x=data.x,
            y=data.y
        )
        position = await crud_asset_position.create_position(db, create_data)

    return position