from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime, date
from typing import Optional, List, Any
from app.schemas.assets.AssetAssignmentSchemas import AssetUserFullResponse

class AssetBase(BaseModel):
    name: str
    inventory_id: str
    serial_number: Optional[str] = None
    asset_status: Optional[str] = None
    asset_status_id: Optional[int] = None
    quantity: Optional[int] = None
    comment: Optional[str] = None
    date_issue: Optional[date] = None
    date_purchasing: Optional[date] = None
    model_id: Optional[int] = None
    model_name: Optional[str] = None
    asset_type_id: Optional[int] = None
    parent_id: Optional[int] = None
    # location_id: Optional[int] = None

    # Еженедельная проверка оборудования
    every_week_check: Optional[bool] = False    # true/false
    next_service: Optional[date] = None         # datetime
    service_period: Optional[int] = None        # Int (count days)

    @field_validator('asset_status', mode='before')
    @classmethod
    def extract_status_string(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        # Если SQLAlchemy отдал объект из relationship
        if hasattr(v, 'status'):
            return v.status
        # Если это уже строка
        if isinstance(v, str):
            return v
        return None

    # Временные поля
    parent_name: Optional[str] = None
    manufacturer_name: Optional[str] = None
    vendor_name: Optional[str] = None
    os_name: Optional[str] = None


class AssetCreate(AssetBase):
    # Для синхронизации привязок пользователей
    users: Optional[List[AssetUserUpdate]] = None
    responsible_users: Optional[List[AssetUserUpdate]] = None
    # Локация на карте
    location: Optional[AssetLocationUpdate] = None

# Схема для обновления привязок пользователей
class AssetUserUpdate(BaseModel):
    """Схема для привязки/отвязки пользователя от актива"""
    employee_id: str

class AssetUpdate(BaseModel):
    name: Optional[str] = None
    inventory_id: Optional[str] = None
    serial_number: Optional[str] = None
    # asset_status: Optional[str] = None
    asset_status_id: Optional[int] = None
    quantity: Optional[int] = None
    comment: Optional[str] = None
    date_issue: Optional[date] = None
    date_purchasing: Optional[date] = None
    model_id: Optional[int] = None
    model_name: Optional[str] = None
    asset_type_id: Optional[int] = None
    parent_id: Optional[int] = None
    # location_id: Optional[int] = None
    location: Optional[AssetLocationUpdate] = None

    # Еженедельная проверка оборудования
    every_week_check: Optional[bool] = False # true/false
    next_service: Optional[date] = None  # datetime
    service_period: Optional[int] = None     # Int (count days or count week ?)

    # Временные поля
    parent_name: Optional[str] = None
    manufacturer_name: Optional[str] = None
    vendor_name: Optional[str] = None
    os_name: Optional[str] = None

    # Для синхронизации привязок пользователей
    users: Optional[List[AssetUserUpdate]] = None
    responsible_users: Optional[List[AssetUserUpdate]] = None

class AssetResponse(AssetBase):
    asset_id: int
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    asset_type_name: Optional[str] = None
    asset_status_id: Optional[int] = None
    # model: Optional["AssetModelResponse"] = None
    # location: Optional[LocationResponse] = None

    location: Optional[AssetLocationResponse] = None

    # Для синхронизации привязок пользователей
    users: Optional[List[AssetUserFullResponse]] = None
    responsible_users: Optional[List[AssetUserFullResponse]] = None

    parent: Optional["AssetParentResponse"] = None

    model_config = ConfigDict(from_attributes=True)

class AssetParentResponse(AssetBase):
    model_config = ConfigDict(from_attributes=True)


class AssetShortResponse(AssetBase):
    asset_id: int
    # model: Optional["AssetModelResponse"] = None
    asset_type_name: Optional[str] = None
    # location: Optional[LocationResponse] = None

    location: Optional[AssetLocationResponse] = None

    model_config = ConfigDict(from_attributes=True)


class AssetLocationUpdate(BaseModel):
    """Схема для обновления позиции актива на карте"""
    workshop_id: int
    place: Optional[str] = None
    level: Optional[int] = None
    x: int
    y: int
    rotation: Optional[int] = 0
    scale: Optional[int] = 100

class AssetLocationResponse(BaseModel):
    """Локация актива на основе Workshop и AssetPosition"""
    workshop_id: int
    place: Optional[str] = None
    level: Optional[int] = None
    x: Optional[int] = None
    y: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)