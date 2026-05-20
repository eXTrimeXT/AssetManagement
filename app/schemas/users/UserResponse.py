from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime
from typing import Optional, Dict

from sqlalchemy.orm import Mapped


class UserBase(BaseModel):
    """Базовая схема пользователя"""
    user_tab_id: Optional[str] = None
    owner: str
    user_en_name: Optional[str] = None
    role: Optional[str] = None
    permissions: Optional[Dict[str, str]] = None
    user_position: Optional[str] = None
    department: Optional[str] = None
    email: EmailStr
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
    owner: str
    user_position: Optional[str] = None
    department: Optional[str] = None
    email: EmailStr

    model_config = ConfigDict(from_attributes=True)