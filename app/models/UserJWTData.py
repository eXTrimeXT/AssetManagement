import json
from datetime import datetime
from typing import Optional, Dict, Any, List

class UserJWTData:
    """Модель данных пользователя, извлеченных из JWT токена"""

# payload =
# {
#     "iat": 1779168375,
#     "exp": 1779211575,
#     "login": "gw07015370",
#     "last_ip": "10.168.135.61",
#     "last_time": "05:03:32 19.05.2026",
#     "department": null,
#     "permissions": [
#         {
#             "calc": "1",
#             "consumption": "1",
#             "cost_add": "1",
#             "cost_check": "0",
#             "cost_history": "1",
#             "cost_leader": "1",
#             "cost_main_leader": "1",
#             "dmr_rules": "1",
#             "email": "1",
#             "groups": "1",
#             "materials": "1",
#             "nominate": "1",
#             "pf_editbatch": "0",
#             "pf_edityearplan": "0",
#             "pf_full_rules": "0",
#             "pf_readgraph": "0",
#             "plan": "1",
#             "qrcode_msk": "1",
#             "qrcode_pda": "1",
#             "qrcode_ps": "1",
#             "stock": "1",
#             "supply": "1",
#             "users": "1",
#             "warehouse": "1",
#             "wh_edit_remains": "1",
#             "wh_inv_change": "1",
#             "wh_inv_read": "1",
#             "wh_read_remains": "1",
#             "wh_topology": "1",
#             "uid": "1",
#             "name_group": "Admin"
#         }
#     ],
#     "user_data": {
#         "email": "Timur.Malyshev@hmmr.ru",
#         "fullname": "Timur Malyshev",
#         "department": "ISSS",
#         "distinguishedName": "CN=Timur Malyshev,OU=INFORMATION SYSTEMS SUPPORT SECTION (ISSS),OU=Russian Digital Center (RDC),OU=Users,OU=HMMR,DC=local,DC=hmmr,DC=ru",
#         "groups": []
#     }
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
        # self.permissions: List[Dict[str, str]] = payload.get("permissions", []) or []

        raw_perms = payload.get("permissions", [])
        if isinstance(raw_perms, str):
            try:
                self.permissions: List[Dict[str, str]] = json.loads(raw_perms)
            except json.JSONDecodeError:
                self.permissions = []
        elif isinstance(raw_perms, list):
            self.permissions = raw_perms
        else:
            self.permissions = []

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
            "permissions": self.permissions,
            "last_ip": self.last_ip,
            "last_time": self.last_time,
            "is_expired": self.is_expired,
        }
