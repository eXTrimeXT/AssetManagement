from pydantic import BaseModel, Field, field_validator, ConfigDict


class AssetPositionCreate(BaseModel):
    """Схема для создания новой позиции актива на карте"""
    asset_id: int = Field(..., gt=0, description="ID актива")
    workshop_id: int = Field(..., gt=0, description="ID цеха")

    # Координаты на карте
    x: int = Field(..., description="Координата X (пиксели)")
    y: int = Field(..., description="Координата Y (пиксели)")
    rotation: int = Field(0, ge=0, lt=360, description="Угол поворота (0-360 градусов)")
    scale: int = Field(100, gt=0, description="Масштаб иконки (проценты)")

    # Статус
    is_active: bool = Field(True, description="Активна ли позиция")

    line: str = Field(..., description="Линия цеха")
    office: str = Field(..., description="Офис")
    room: str = Field(..., description="Помещение")
    floor: str = Field(..., description="Этаж")

    @field_validator('x', 'y')
    @classmethod
    def validate_coordinates(cls, v: int) -> int:
        """Валидация координат"""
        if v < 0:
            raise ValueError("Координаты не могут быть отрицательными")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "asset_id": 1,
                "workshop_id": 1,
                "x": 250,
                "y": 150,
                "rotation": 0,
                "scale": 100,
                "is_active": True,
                "line": "line",
                "office": "office",
                "room": "room",
                "floor": "floor"
            }
        }