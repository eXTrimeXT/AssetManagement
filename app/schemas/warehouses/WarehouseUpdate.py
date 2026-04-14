from pydantic import BaseModel, Field
from typing import Optional

class WarehouseUpdate(BaseModel):
    """Схема для обновления склада"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    location_id: Optional[int] = None
    prepared_by: Optional[int] = None