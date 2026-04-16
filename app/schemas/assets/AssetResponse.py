from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import Optional, List

from app.schemas.locations.LocationResponse import LocationResponse


class AssetBase(BaseModel):
    """Базовая схема актива"""
    name: str
    inventory_id: str
    serial_number: str
    asset_type_id: int
    asset_status: str
    type_domain: Optional[str] = None
    affixed_inventory_id: Optional[bool] = None
    info_storage_location: Optional[str] = None
    location_id: Optional[int] = None
    passwork: Optional[str] = None
    date_issue: Optional[date] = None
    date_purchasing: Optional[date] = None
    comment: Optional[str] = None
    parent_id: Optional[int] = None
    prepared_by: Optional[int] = None
    checked_by: Optional[int] = None
    software_id: Optional[int] = None

    manufacturer_id: Optional[int] = None
    vendor_id: Optional[int] = None

class AssetResponse(AssetBase):
    """Полная схема ответа"""
    asset_id: int
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    location_obj: Optional[LocationResponse] = None

    model_config = ConfigDict(from_attributes=True)

class AssetShortResponse(BaseModel):
    """Краткая схема для списков"""
    asset_id: int
    name: str
    inventory_id: str
    serial_number: str
    asset_status: str
    asset_type_id: int
    location_id: Optional[int] = None
    parent_id: Optional[int] = None
    software_id: Optional[int] = None
    manufacturer_id: Optional[int] = None
    vendor_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)