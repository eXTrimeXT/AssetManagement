from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class AssetPositionResponse(BaseModel):
    """Схема ответа с информацией о позиции актива на карте"""
    id: Optional[int] = None
    asset_id: Optional[int] = None
    workshop_id: Optional[int] = None

    # Координаты на карте
    x: Optional[int] = None
    y: Optional[int] = None
    rotation: Optional[int] = None
    scale: Optional[int] = None

    # Статус
    is_active: Optional[bool] = None

    place: Optional[str] = None
    level: Optional[int] = None

    # Служебные поля
    created_at: Optional[datetime] = Field(None, description="Дата создания")
    updated_at: Optional[datetime] = Field(None, description="Дата обновления")

    model_config = ConfigDict(from_attributes=True)