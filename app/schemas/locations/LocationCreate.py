from pydantic import BaseModel, Field
from typing import Optional

class LocationCreate(BaseModel):
    """Схема для создания новой локации"""
    country: str = Field(..., min_length=2, max_length=100, description="Страна")
    city: str = Field(..., min_length=2, max_length=100, description="Город")
    address: str = Field(..., min_length=5, max_length=255, description="Адрес (улица, дом)")
    room: Optional[str] = Field(None, max_length=50, description="Помещение/Кабинет")
    floor: Optional[str] = Field(None, max_length=10, description="Этаж")