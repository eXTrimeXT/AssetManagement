from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, Any


# class UserCreate(BaseModel):
#     """Схема для создания нового пользователя"""
#
#     user_tab_id: Optional[str] = None       # Табельный номер
#     owner: Optional[str] = None             # ФИО на русском (обязательно)
#     user_en_name: Optional[str] = None      # ФИО на английском
#     user_position: Optional[str] = None     # Должность
#     department_id: Optional[int] = None     # Департамент
#     division_id: Optional[int] = None       # Отдел
#     group_id: Optional[int] = None          # Группа
#     email: Optional[str] = None             # Email
#     phone: Optional[str] = None             # Телефон
#     is_active: bool = True                  # Статус по умолчанию
#     comment: Optional[Any] = None           # Комментарий
#
#     model_config = ConfigDict(json_schema_extra={
#         "example": {
#             "user_tab_id": "12345",
#             "owner": "Иванов Иван Иванович",
#             "comment": "Комментарий"
#         }
#     })