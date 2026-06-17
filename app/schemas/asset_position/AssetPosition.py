from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


# === БАЗОВАЯ СХЕМА (для создания) ===
class AssetPositionCreate(BaseModel):
    """
    Схема для создания позиции актива на карте.
    """
    asset_id: int = Field(..., gt=0, description="ID актива")
    workshop_id: int = Field(..., gt=0, description="ID цеха")

    x: int = Field(..., ge=0, description="Координата X (пиксели)")
    y: int = Field(..., ge=0, description="Координата Y (пиксели)")
    rotation: Optional[int] = Field(0, ge=0, lt=360, description="Угол поворота (градусы)")
    scale: Optional[int] = Field(100, ge=10, le=500, description="Масштаб (проценты)")


# === СХЕМА ДЛЯ ОБНОВЛЕНИЯ ===
class AssetPositionUpdate(BaseModel):
    """
    Схема для обновления позиции актива.
    """
    x: Optional[int] = Field(None, ge=0)
    y: Optional[int] = Field(None, ge=0)
    rotation: Optional[int] = Field(None, ge=0, lt=360)
    scale: Optional[int] = Field(None, ge=10, le=500)
    is_active: Optional[bool] = None


# === СХЕМА ДЛЯ ПЕРЕМЕЩЕНИЯ АКТИВА ===
class AssetPositionMove(BaseModel):
    """
    Схема для быстрого перемещения актива (только координаты).
    """
    x: int = Field(..., ge=0, description="Новая координата X")
    y: int = Field(..., ge=0, description="Новая координата Y")


# === СХЕМА ОТВЕТА ===
class AssetPositionResponse(BaseModel):
    """
    Схема ответа с позицией актива.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    workshop_id: int

    x: int
    y: int
    rotation: int
    scale: int

    is_active: bool

    created_at: datetime
    updated_at: datetime


# === РАСШИРЕННАЯ СХЕМА (с данными актива) ===
class AssetPositionWithAssetResponse(AssetPositionResponse):
    """
    Позиция с полной информацией об активе.
    """
    asset_name: Optional[str] = None
    asset_inventory_id: Optional[str] = None
    asset_serial_number: Optional[str] = None
    asset_type: Optional[str] = None


# === СХЕМА ДЛЯ СПИСКА ПОЗИЦИЙ ===
class AssetPositionListResponse(BaseModel):
    """
    Схема для списка позиций на карте цеха.
    """
    workshop_id: int
    positions: list[AssetPositionWithAssetResponse]
    total_count: int