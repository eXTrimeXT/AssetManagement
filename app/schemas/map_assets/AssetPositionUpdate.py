from typing import Optional
from pydantic import BaseModel, Field, field_validator


class AssetPositionUpdate(BaseModel):
    """Схема для обновления позиции актива на карте"""
    # Координаты на карте
    x: Optional[int] = Field(None, description="Координата X (пиксели)")
    y: Optional[int] = Field(None, description="Координата Y (пиксели)")
    rotation: Optional[int] = Field(None, ge=0, lt=360, description="Угол поворота (0-360 градусов)")
    scale: Optional[int] = Field(None, gt=0, description="Масштаб иконки (проценты)")

    # Статус
    is_active: Optional[bool] = Field(None, description="Активна ли позиция")

    @field_validator('x', 'y')
    @classmethod
    def validate_coordinates(cls, v: Optional[int]) -> Optional[int]:
        """Валидация координат"""
        if v is None:
            return v
        if v < 0:
            raise ValueError("Координаты не могут быть отрицательными")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "x": 300,
                "y": 200,
                "rotation": 45
            }
        }