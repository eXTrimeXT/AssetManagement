from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

from app.schemas.users.UserResponse import UserResponse


class SoftwareBase(BaseModel):
    """Базовая схема ПО"""
    office_type: Optional[str] = None
    office_key: Optional[str] = None
    os_type: Optional[str] = None
    os_key: Optional[str] = None
    remote_control: Optional[str] = None
    admin_permission: bool = False
    who_installed: Optional[int] = None
    installed_at: Optional[datetime] = None
    comment: Optional[str] = None

class SoftwareResponse(SoftwareBase):
    """Полная схема ответа"""
    software_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    installer: Optional[UserResponse] = Field(default=None)

    model_config = ConfigDict(from_attributes=True)

class SoftwareShortResponse(BaseModel):
    """Краткая схема для списков"""
    software_id: int
    office_type: Optional[str] = None
    os_type: Optional[str] = None
    admin_permission: bool
    who_installed: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)