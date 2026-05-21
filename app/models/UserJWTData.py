from datetime import datetime
from typing import Optional, Dict, Any, List, Literal

class UserJWTData:
    """Модель данных пользователя, извлеченных из JWT токена"""

    def __init__(self, payload: Dict[str, Any]):
        # Базовые поля из корня payload
        self.login: str = payload.get("login", "")
        self.last_ip: Optional[str] = payload.get("last_ip")
        self.last_time: Optional[str] = payload.get("last_time")

        # Вложенные данные из user_data
        user_data = payload.get("user_data", {}) or {}
        self.department: Optional[str] = user_data.get("department")
        self.email: Optional[str] = user_data.get("email")
        self.fullname: Optional[str] = user_data.get("fullname")
        self.distinguished_name: Optional[str] = user_data.get("distinguishedName")
        self.groups: List[str] = user_data.get("groups", []) or []

        # === НОВЫЙ ФОРМАТ: преобразуем список [{name_group, read, write}] в dict {group: {read, write}} ===
        raw_perms = payload.get("permissions", [])
        self.permissions: Dict[str, Dict[str, bool]] = {}

        if isinstance(raw_perms, list):
            for perm in raw_perms:
                if isinstance(perm, dict):
                    name_group = perm.get("name_group")
                    if name_group:
                        self.permissions[name_group] = {
                            "read": bool(perm.get("read", False)),
                            "write": bool(perm.get("write", False))
                        }
        elif isinstance(raw_perms, str):
            import json
            try:
                parsed = json.loads(raw_perms)
                for perm in parsed:
                    if isinstance(perm, dict):
                        name_group = perm.get("name_group")
                        if name_group:
                            self.permissions[name_group] = {
                                "read": bool(perm.get("read", False)),
                                "write": bool(perm.get("write", False))
                            }
            except:
                pass

        # Timestamps
        self.iat: Optional[int] = payload.get("iat")
        self.exp: Optional[int] = payload.get("exp")

    @property
    def is_expired(self) -> bool:
        if not self.exp:
            return True
        return datetime.utcnow().timestamp() > self.exp

    def has_access(self, group: str, access_type: Literal["read", "write"]) -> bool:
        """Проверка доступа: group='computer', access_type='read' или 'write'"""
        perms = self.permissions.get(group)
        if not perms:
            return False
        return perms.get(access_type) is True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "login": self.login,
            "email": self.email,
            "fullname": self.fullname,
            "department": self.department,
            "distinguished_name": self.distinguished_name,
            "groups": self.groups,
            "permissions": self.permissions,  # Теперь {"computer": {"read": false, "write": true}, ...}
            "last_ip": self.last_ip,
            "last_time": self.last_time,
            "is_expired": self.is_expired,
        }