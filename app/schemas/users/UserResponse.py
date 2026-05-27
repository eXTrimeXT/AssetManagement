from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime
from typing import Optional, Dict, Union


class UserBase(BaseModel):
    """Базовая схема пользователя"""
    user_tab_id: Optional[str] = None
    owner: str
    user_en_name: Optional[str] = None
    # permissions: Dict[str, Union[Dict[str, bool], str, bool]] = {}
    permissions: Dict[str, Dict[str, bool]] = {}
    user_position: Optional[str] = None
    department_id: Optional[int] = None
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
    department_id: Optional[int] = None
    email: EmailStr

    model_config = ConfigDict(from_attributes=True)