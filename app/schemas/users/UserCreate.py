from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional

class UserCreate(BaseModel):
    """Схема для создания нового пользователя"""

    user_tab_id: Optional[str] = None       # Табельный номер (не обязателен)
    owner: Optional[str] = None             # ФИО на русском (обязательно)
    user_en_name: Optional[str] = None      # ФИО на английском
    user_position: Optional[str] = None     # Должность
    department_id: Optional[int] = None     # Отдел
    email: Optional[EmailStr] = None        # Email (валидация формата)
    phone: Optional[str] = None             # Телефон
    is_active: bool = True                  # Статус по умолчанию

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "user_tab_id": "12345",
            "owner": "Иванов Иван Иванович",
            "user_en_name": "Ivanov Ivan",
            "user_position": "Инженер",
            "department_id": "RDC",
            "email": "ivanov@company.com",
            "phone": "+7 (999) 123-45-67",
            "is_active": True,
            "role": "user"
        }
    })