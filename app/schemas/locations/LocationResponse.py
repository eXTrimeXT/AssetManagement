from pydantic import BaseModel, ConfigDict
from typing import Optional

class LocationResponse(BaseModel):
    """Полная схема ответа"""
    location_id: int
    country: str
    city: str
    address: str
    room: Optional[str] = None
    floor: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class LocationShortResponse(BaseModel):
    """Краткая схема для списков"""
    location_id: int
    city: str
    address: str
    room: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)