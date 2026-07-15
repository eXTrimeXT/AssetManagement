from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class WorkshopCreate(BaseModel):
    """Схема для создания нового цеха"""
    name: str = Field(..., min_length=1, max_length=255, description="Название цеха")
    code: str = Field(..., min_length=1, max_length=50, description="Уникальный код цеха")
    description: Optional[str] = Field(None, description="Описание цеха")

    # Карта цеха
    background_image_url: Optional[str] = Field(None, max_length=500, description="Путь к фону (плану цеха)")

    # Геометрия цеха
    geometry: Optional[Dict[str, Any]] = Field(None, description="Геометрия цеха для сложных форм")
    workshop_width: Optional[int] = Field(None, gt=0, description="Ширина цеха (если прямоугольная форма)")
    workshop_height: Optional[int] = Field(None, gt=0, description="Высота цеха (если прямоугольная форма)")

    # Позиция на общей карте
    offset_x: int = Field(0, description="Смещение по X на общей карте")
    offset_y: int = Field(0, description="Смещение по Y на общей карте")

    # Масштаб и цвет
    workshop_scale: float = Field(1.0, gt=0, description="Масштаб цеха")
    color: Optional[str] = Field("#546E7A", max_length=20, description="Цвет цеха (hex формат)")

    # Статус
    is_active: bool = Field(True, description="Активен ли цех")

    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Валидация кода цеха"""
        if not v.strip():
            raise ValueError("Код цеха не может быть пустым")
        return v.strip().upper()

    @field_validator('color')
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        """Валидация цвета в hex формате"""
        if v is None:
            return v
        v = v.strip()
        if not v.startswith('#'):
            raise ValueError("Цвет должен быть в hex формате (#RRGGBB или #RRGGBBAA)")
        if len(v) not in [7, 9]:  # #RRGGBB или #RRGGBBAA
            raise ValueError("Цвет должен быть в формате #RRGGBB или #RRGGBBAA")
        return v

    class Config:
        json_schema_extra = {
            "example": {
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
                "is_active": True
            }
        }