from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Dict, List

class UserBase(BaseModel):
    """Базовая схема пользователя"""
    user_tab_id: Optional[str] = None
    owner: Optional[str] = None
    user_en_name: Optional[str] = None
    assets_admin: Optional[bool] = None
    permissions: Optional[Dict[str, Dict[str, bool]]] = {}
    user_position: Optional[str] = None
    comment: Optional[str] = None

    email: Optional[str] = None
    phone: Optional[str] = None

    department_id: Optional[int] = None
    division_id: Optional[int] = None
    group_id: Optional[int] = None


class UserResponse(UserBase):
    """Схема ответа с полным набором полей"""
    department_abbreviation: Optional[str] = None
    division_abbreviation: Optional[str] = None
    group_abbreviation: Optional[str] = None

    # user_id: int
    user_tab_id: Optional[str] = None

    is_active: bool

    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class AssetForUserResponse(BaseModel):
    """Краткая схема для списков"""
    asset_id: int
    name: str
    inventory_id: str
    serial_number: Optional[str]
    asset_status: str
    comment: Optional[str] = None

    model_id: Optional[int] = None
    model_name: Optional[str] = None

    class_id: Optional[int] = None
    class_name: Optional[str] = None

    asset_type_id: Optional[int] = None
    type_asset_en_name: Optional[str] = None
    type_asset_name: Optional[str] = None

    warehouse_id: Optional[int] = None
    warehouse_name: Optional[str] = None

    parent_id: Optional[int] = None
    parent_name: Optional[str] = None

    software_id: Optional[int] = None
    software_office_type: Optional[str] = None

    manufacturer_id: Optional[int] = None
    manufacturer_name: Optional[str] = None

    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class UserShortResponse(BaseModel):
    """Краткая схема для списков (без назначений)"""
    # user_id: int
    user_tab_id: Optional[str] = None
    owner: Optional[str] = None
    user_position: Optional[str] = None
    comment: Optional[str] = None
    department_id: Optional[int] = None
    division_id: Optional[int] = None
    group_id: Optional[int] = None
    email: Optional[str] = None
    permissions: Optional[Dict[str, Dict[str, bool]]] = {}

    assets: List[AssetForUserResponse] = []

    model_config = ConfigDict(from_attributes=True)