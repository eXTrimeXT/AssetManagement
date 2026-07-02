from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date


class UserInAssetUpdate(BaseModel):
    """Схема пользователя для обновления актива"""
    # user_id: int
    user_tab_id: Optional[str] = None
    owner: Optional[str] = None
    user_position: Optional[str] = None
    comment: Optional[str] = None
    department_id: Optional[int] = None
    division_id: Optional[int] = None
    group_id: Optional[int] = None
    email: Optional[str] = None
    selected: bool = False  # Флаг: выбран ли пользователь


class AssetUpdateWithUsers(BaseModel):
    """Схема для обновления актива с привязкой пользователей"""

    asset_id: Optional[int] = None
    name: Optional[str] = None
    inventory_id: Optional[str] = None
    serial_number: Optional[str] = None
    asset_status: Optional[str] = None
    comment: Optional[str] = None
    model_id: Optional[int] = None
    parent_id: Optional[int] = None
    software_id: Optional[int] = None
    manufacturer_id: Optional[int] = None
    vendor_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    workshop_id: Optional[int] = None

    # Даты
    date_issue: Optional[date] = None
    date_purchasing: Optional[date] = None

    # Флаги
    affixed_inventory_id: Optional[bool] = None

    # Список пользователей
    users: List[UserInAssetUpdate] = []