from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from typing import Optional, List
from app.schemas.assets.asset_assignment import AssetUserResponse
from app.schemas.locations.LocationResponse import LocationResponse


class AssetBase(BaseModel):
    name: str
    inventory_id: str
    serial_number: Optional[str] = None
    asset_status: Optional[str] = "Приемка"
    comment: Optional[str] = None
    date_issue: Optional[date] = None
    date_purchasing: Optional[date] = None
    model_id: Optional[int] = None
    model_name: Optional[str] = None
    asset_type_id: Optional[int] = None
    parent_id: Optional[int] = None
    location_id: Optional[int] = None
    prepared_by: Optional[str] = None
    checked_by: Optional[str] = None


class AssetCreate(AssetBase):
    pass

# Схема для обновления привязок пользователей
class AssetUserUpdate(BaseModel):
    """Схема для привязки/отвязки пользователя от актива"""
    employee_id: str

class AssetUpdate(BaseModel):
    name: Optional[str] = None
    inventory_id: Optional[str] = None
    serial_number: Optional[str] = None
    asset_status: Optional[str] = None
    comment: Optional[str] = None
    date_issue: Optional[date] = None
    date_purchasing: Optional[date] = None
    model_id: Optional[int] = None
    model_name: Optional[str] = None
    asset_type_id: Optional[int] = None
    parent_id: Optional[int] = None
    location_id: Optional[int] = None
    prepared_by: Optional[str] = None
    checked_by: Optional[str] = None

    # Для синхронизации привязок пользователей
    users: Optional[List[AssetUserUpdate]] = None


class AssetResponse(AssetBase):
    asset_id: int
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    # model: Optional["AssetModelResponse"] = None
    # asset_type: Optional[AssetTypeResponse] = None
    location: Optional[LocationResponse] = None
    parent: Optional["AssetResponse"] = None
    asset_type_name: Optional[str] = None

    users: Optional[List[AssetUserResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class AssetShortResponse(AssetBase):
    asset_id: int
    # model: Optional["AssetModelResponse"] = None
    # asset_type: Optional[AssetTypeResponse] = None
    asset_type_name: Optional[str] = None
    location: Optional[LocationResponse] = None

    model_config = ConfigDict(from_attributes=True)