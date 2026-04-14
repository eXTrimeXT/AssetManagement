from pydantic import BaseModel, Field
from typing import Optional

class WarehouseCreate(BaseModel):
    """Схема для создания склада"""
    name: str = Field(..., min_length=2, max_length=100, description="Название склада")
    location_id: Optional[int] = Field(None, description="ID локации (адреса) склада")
    prepared_by: Optional[int] = Field(None, description="ID ответственного сотрудника")