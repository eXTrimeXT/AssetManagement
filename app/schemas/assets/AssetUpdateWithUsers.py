from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date


class UserInAssetUpdate(BaseModel):
    """Схема пользователя для обновления актива"""
    user_id: int
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

    # Обязательные поля
    asset_id: int
    name: str = Field(..., min_length=1, max_length=150)
    inventory_id: str = Field(..., min_length=1, max_length=50)
    serial_number: Optional[str] = Field(None, max_length=100)
    asset_status: str = Field(default="Приемка", max_length=50)

    # Опциональные поля
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