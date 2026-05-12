from datetime import datetime
from typing import Optional, Dict, Any, List

class UserJWTData:
    """Модель данных пользователя, извлеченных из JWT токена"""

    def __init__(self, payload: Dict[str, Any]):
        # Базовые поля из корня payload
        self.login: str = payload.get("login", "")
        self.last_ip: Optional[str] = payload.get("last_ip")
        self.last_time: Optional[str] = payload.get("last_time")
        self.department: Optional[str] = payload.get("department")

        # Вложенные данные из user_data
        user_data = payload.get("user_data", {}) or {}
        self.email: Optional[str] = user_data.get("email")
        self.fullname: Optional[str] = user_data.get("fullname")
        self.distinguished_name: Optional[str] = user_data.get("distinguishedName")
        self.groups: List[str] = user_data.get("groups", []) or []

        # Timestamps
        self.iat: Optional[int] = payload.get("iat")  # issued at
        self.exp: Optional[int] = payload.get("exp")  # expiration

    @property
    def is_expired(self) -> bool:
        """Проверяет, истек ли срок действия токена"""
        if not self.exp:
            return True
        return datetime.utcnow().timestamp() > self.exp

    def has_permission(self, permission: str) -> bool:
        """
        Проверка наличия права доступа.
        Реализуй свою логику на основе groups/department.
        """
        # Пример: админы имеют все права
        if "admin" in self.groups:
            return True
        # Пример: доступ по отделу
        # if self.department == "ISSS" and permission in ["read", "write"]:
        #     return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Возвращает данные пользователя как словарь"""
        return {
            "login": self.login,
            "email": self.email,
            "fullname": self.fullname,
            "department": self.department,
            "distinguished_name": self.distinguished_name,
            "groups": self.groups,
            "last_ip": self.last_ip,
            "last_time": self.last_time,
            "is_expired": self.is_expired,
        }
