from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

class SoftwareUpdate(BaseModel):
    """Схема для обновления записи о ПО"""

    office_type: Optional[str] = Field(None, max_length=100)
    office_key: Optional[str] = Field(None, max_length=100)
    os_type: Optional[str] = Field(None, max_length=100)
    os_key: Optional[str] = Field(None, max_length=100)
    remote_control: Optional[str] = Field(None, max_length=150)
    admin_permission: Optional[bool] = None
    who_installed: Optional[str] = Field(None, max_length=150)
    installed_at: Optional[datetime] = None
    comment: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra='ignore')