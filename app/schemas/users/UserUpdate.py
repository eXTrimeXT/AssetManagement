from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any


# class UserUpdate(BaseModel):
#     """Схема для обновления пользователя (все поля опциональны)"""
#     user_tab_id: Optional[str] = None
#     owner: Optional[str] = None
#     user_en_name: Optional[str] = None
#     user_position: Optional[str] = None
#     comment: Optional[Any] = None
#     department_id: Optional[int] = None
#     division_id: Optional[int] = None
#     group_id: Optional[int] = None
#     email: Optional[str] = None
#     phone: Optional[str] = None
#     is_active: Optional[bool] = None
#
#     model_config = ConfigDict(json_schema_extra={
#         "example": {
#             "owner": "Иванов Иван Иванович (обновлено)",
#             "department_id": 1,
#             "is_active": "True"
#         }
#     })

# class PermissionsUpdate(BaseModel):
#     """Схема для обновления прав пользователя"""
#     permissions: Dict[str, Dict[str, bool]]
#     model_config = ConfigDict(json_schema_extra={
#         "example": {
#             "permissions": {
#                 "group1": {
#                     "read": True,
#                     "write": False
#                 },
#                 "group2": {
#                     "read": True,
#                     "write": False
#                 }
#             }
#         }
#     })