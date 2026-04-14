from pydantic import BaseModel, ConfigDict
from typing import Optional
from app.schemas.locations.LocationResponse import LocationShortResponse
from app.schemas.users.UserResponse import UserShortResponse

class WarehouseBase(BaseModel):
    name: str
    location_id: Optional[int] = None
    prepared_by: Optional[int] = None

class WarehouseResponse(WarehouseBase):
    warehouse_id: int
    # Вложенные объекты для удобного ответа (опционально, можно убрать если нужны только ID)
    location: Optional[LocationShortResponse] = None
    manager: Optional[UserShortResponse] = None

    model_config = ConfigDict(from_attributes=True)

class WarehouseShortResponse(BaseModel):
    warehouse_id: int
    name: str
    location_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)