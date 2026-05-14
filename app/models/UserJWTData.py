from datetime import datetime
from typing import Optional, Dict, Any, List

class UserJWTData:
    """Модель данных пользователя, извлеченных из JWT токена"""

# payload={
    # 'iat': 1778742506,
    # 'exp': 1778785706,
    # 'login': 'gw07015370',
    # 'last_ip': '10.168.135.61',
    # 'last_time': '13:07:14 13.05.2026',
    # 'department': None,
    # 'user_data':
    # {
        # 'email': 'Timur.Malyshev@hmmr.ru',
        # 'fullname': 'Timur Malyshev',
        # 'department': 'ISSS',
        # 'distinguishedName': 'CN=Timur Malyshev,OU=INFORMATION SYSTEMS SUPPORT SECTION (ISSS),OU=Russian Digital Center (RDC),OU=Users,OU=HMMR,DC=local,DC=hmmr,DC=ru',
        # 'groups': []
    # }
# }

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
