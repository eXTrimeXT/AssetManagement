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

    place: Optional[str] = None
    level: Optional[int] = None

    # Служебные поля
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: Optional[datetime] = Field(None, description="Дата обновления")

    model_config = ConfigDict(from_attributes=True)