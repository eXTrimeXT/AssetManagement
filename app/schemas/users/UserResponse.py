from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime
from typing import Optional, Dict


class UserBase(BaseModel):
    """Базовая схема пользователя"""
    user_tab_id: Optional[str] = None
    owner: Optional[str] = None
    user_en_name: Optional[str] = None
    permissions: Optional[Dict[str, Dict[str, bool]]] = {}
    user_position: Optional[str] = None

    department_id: Optional[int] = None
    division_id: Optional[int] = None
    group_id: Optional[int] = None

    email: Optional[EmailStr] = None
    phone: Optional[str] = None

class UserResponse(UserBase):
    """Схема ответа с полным набором полей"""
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class UserShortResponse(BaseModel):
    """Краткая схема для списков (без назначений)"""
    user_id: int
    user_tab_id: Optional[str] = None
    owner: Optional[str] = None
    user_position: Optional[str] = None
    department_id: Optional[int] = None
    division_id: Optional[int] = None
    group_id: Optional[int] = None
    email: Optional[EmailStr] = None

    model_config = ConfigDict(from_attributes=True)