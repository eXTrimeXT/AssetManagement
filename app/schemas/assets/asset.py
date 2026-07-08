from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from typing import Optional, List
from app.schemas.assets.asset_model import AssetModelResponse
from app.schemas.assets.asset_assignment import AssetAssignmentShortResponse
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
    asset_type_id: Optional[int] = None
    parent_id: Optional[int] = None
    location_id: Optional[int] = None
    prepared_by: Optional[str] = None
    checked_by: Optional[str] = None


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    inventory_id: Optional[str] = None
    serial_number: Optional[str] = None
    asset_status: Optional[str] = None
    comment: Optional[str] = None
    date_issue: Optional[date] = None
    date_purchasing: Optional[date] = None
    model_id: Optional[int] = None
    parent_id: Optional[int] = None
    location_id: Optional[int] = None
    prepared_by: Optional[str] = None
    checked_by: Optional[str] = None


class AssetResponse(AssetBase):
    asset_id: int
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model: Optional[AssetModelResponse] = None
    location: Optional[LocationResponse] = None

    # current_users: Optional[List[AssetAssignmentShortResponse]] = []  # Активные пользователи

    model_config = ConfigDict(from_attributes=True)


class AssetShortResponse(AssetBase):
    asset_id: int
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model: Optional[AssetModelResponse] = None
    location: Optional[LocationResponse] = None

    model_config = ConfigDict(from_attributes=True)