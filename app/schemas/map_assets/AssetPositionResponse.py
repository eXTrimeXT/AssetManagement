from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class AssetPositionResponse(BaseModel):
    """Схема ответа с информацией о позиции актива на карте"""
    id: int = Field(..., description="ID позиции")
    asset_id: int = Field(..., description="ID актива")
    workshop_id: int = Field(..., description="ID цеха")

    # Координаты на карте
    x: int = Field(..., description="Координата X (пиксели)")
    y: int = Field(..., description="Координата Y (пиксели)")
    rotation: int = Field(..., description="Угол поворота (0-360 градусов)")
    scale: int = Field(..., description="Масштаб иконки (проценты)")

    # Статус
    is_active: bool = Field(..., description="Активна ли позиция")

    # Служебные поля
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: Optional[datetime] = Field(None, description="Дата обновления")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "asset_id": 1,
                "workshop_id": 1,
                "x": 250,
                "y": 150,
                "rotation": 0,
                "scale": 100,
                "is_active": True,
                "created_at": "2026-01-15T10:30:00",
                "updated_at": "2026-01-15T10:30:00"
            }
        }

    # model_config = ConfigDict(from_attributes=True)