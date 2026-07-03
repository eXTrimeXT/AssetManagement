from pydantic import BaseModel, Field
from typing import Optional

class LocationUpdate(BaseModel):
    """Схема для обновления локации (все поля опциональны)"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    country: Optional[str] = Field(None, min_length=2, max_length=100)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    address: Optional[str] = Field(None, min_length=5, max_length=255)
    room: Optional[str] = Field(None, max_length=50)
    floor: Optional[str] = Field(None, max_length=20)