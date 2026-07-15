from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# from app.schemas.map_assets.AssetPositionResponse import AssetPositionResponse

class WorkshopResponse(BaseModel):
    """Схема ответа с информацией о цехе"""
    workshop_id: int = Field(..., description="ID цеха")
    name: str = Field(..., description="Название цеха")
    code: str = Field(..., description="Код цеха")
    description: Optional[str] = Field(None, description="Описание цеха")

    # Карта цеха
    background_image_url: Optional[str] = Field(None, description="Путь к фону")

    # Геометрия цеха
    geometry: Optional[Dict[str, Any]] = Field(None, description="Геометрия цеха")
    workshop_width: Optional[int] = Field(None, description="Ширина цеха")
    workshop_height: Optional[int] = Field(None, description="Высота цеха")

    # Позиция на общей карте
    offset_x: int = Field(..., description="Смещение по X")
    offset_y: int = Field(..., description="Смещение по Y")

    # Масштаб и цвет
    workshop_scale: float = Field(..., description="Масштаб цеха")
    color: Optional[str] = Field(None, description="Цвет цеха")

    # Статус
    is_active: bool = Field(..., description="Активен ли цех")

    # Служебные поля
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: Optional[datetime] = Field(None, description="Дата обновления")

    # Связанные данные (опционально)
    # asset_positions: Optional[List[AssetPositionResponse]] = Field(
    #     None,
    #     description="Список позиций активов в цехе"
    # )

    class Config:
        json_schema_extra = {
            "example": {
                "workshop_id": 1,
                "name": "Цех №1",
                "code": "ЦЕХ-001",
                "description": "Главный производственный цех",
                "background_image_url": "/static/images/workshop_1.png",
                "workshop_width": 800,
                "workshop_height": 600,
                "offset_x": 100,
                "offset_y": 50,
                "workshop_scale": 1.0,
                "color": "#546E7A",
                "is_active": True,
                "created_at": "2026-01-15T10:30:00",
                "updated_at": "2026-01-15T10:30:00",
                "asset_positions": []
            }
        }

    # model_config = ConfigDict(from_attributes=True)