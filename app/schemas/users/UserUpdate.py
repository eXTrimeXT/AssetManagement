from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, Dict


class UserUpdate(BaseModel):
    """Схема для обновления пользователя (все поля опциональны)"""

    user_tab_id: Optional[str] = None
    owner: Optional[str] = None
    user_en_name: Optional[str] = None
    role: Optional[str] = None
    user_position: Optional[str] = None
    department: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "owner": "Иванов Иван Иванович (обновлено)",
            "department": "Отдел разработки",
            "is_active": "True"
        }
    })

class PermissionsUpdate(BaseModel):
    """Схема для обновления прав пользователя"""
    permissions: Dict[str, str]