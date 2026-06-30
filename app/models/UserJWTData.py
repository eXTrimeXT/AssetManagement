from datetime import datetime
from typing import Optional, Dict, Any, List, Literal

# {
#     "user_id": 4,
#     "login": "gw07015370",
#     "email": "Timur.Malyshev@hmmr.ru",
#     "fullname": "Timur Malyshev",
#     "distinguished_name": "CN=Timur Malyshev,OU=SOFTWARE DEVELOPMENT GROUP (SDG),OU=INFORMATION SYSTEMS SUPPORT SECTION (ISSS),OU=Russian Digital Center (RDC),OU=Users,OU=HMMR,DC=local,DC=hmmr,DC=ru",
#     "department": "SDG",
#     "groups": [],
#     "permissions": {
#         "computer": {
#             "read": false,
#             "write": false
#         },
#         "mes_equipment": {
#             "read": false,
#             "write": true
#         },
#         "supplies": {
#             "read": true,
#             "write": false
#         },
#         "power_adapter": {
#             "read": true,
#             "write": true
#         },
#         "data_collection_equipment": {
#             "read": true,
#             "write": true
#         },
#         "Accessories": {
#             "read": true,
#             "write": true
#         },
#         "network_equipment": {
#             "read": true,
#             "write": true
#         },
#         "printing_equipment": {
#             "read": true,
#             "write": true
#         },
#         "server_hardware": {
#             "read": true,
#             "write": true
#         },
#         "users": {
#             "read": true,
#             "write": true
#         },
#         "usersMU": {
#             "read": true,
#             "write": true
#         },
#         "AssetsMU": {
#             "read": true,
#             "write": true
#         }
#     },
#     "assets_admin": true,
#     "last_ip": "172.18.0.2",
#     "last_time": "11:44:33 30.06.2026",
#     "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3ODI4MjQyMTAsImV4cCI6MTc4Mjg2NzQxMCwibG9naW4iOiJndzA3MDE1MzcwIiwibGFzdF9pcCI6IjE3Mi4xOC4wLjIiLCJsYXN0X3RpbWUiOiIxMTo0NDozMyAzMC4wNi4yMDI2IiwiZGVwYXJ0bWVudCI6bnVsbCwicGVybWlzc2lvbnMiOlt7Im5hbWVfZ3JvdXAiOiJjb21wdXRlciIsInJlYWQiOmZhbHNlLCJ3cml0ZSI6ZmFsc2V9LHsibmFtZV9ncm91cCI6Im1lc19lcXVpcG1lbnQiLCJyZWFkIjpmYWxzZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6InN1cHBsaWVzIiwicmVhZCI6dHJ1ZSwid3JpdGUiOmZhbHNlfSx7Im5hbWVfZ3JvdXAiOiJwb3dlcl9hZGFwdGVyIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6ImRhdGFfY29sbGVjdGlvbl9lcXVpcG1lbnQiLCJyZWFkIjp0cnVlLCJ3cml0ZSI6dHJ1ZX0seyJuYW1lX2dyb3VwIjoiQWNjZXNzb3JpZXMiLCJyZWFkIjp0cnVlLCJ3cml0ZSI6dHJ1ZX0seyJuYW1lX2dyb3VwIjoibmV0d29ya19lcXVpcG1lbnQiLCJyZWFkIjp0cnVlLCJ3cml0ZSI6dHJ1ZX0seyJuYW1lX2dyb3VwIjoicHJpbnRpbmdfZXF1aXBtZW50IiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6InNlcnZlcl9oYXJkd2FyZSIsInJlYWQiOnRydWUsIndyaXRlIjp0cnVlfSx7Im5hbWVfZ3JvdXAiOiJ1c2VycyIsInJlYWQiOnRydWUsIndyaXRlIjp0cnVlfSx7Im5hbWVfZ3JvdXAiOiJ1c2Vyc01VIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6IkFzc2V0c01VIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9XSwiYXNzZXRzX2FkbWluIjp0cnVlLCJ1c2VyX2RhdGEiOnsiZW1haWwiOiJUaW11ci5NYWx5c2hldkBobW1yLnJ1IiwiZnVsbG5hbWUiOiJUaW11ciBNYWx5c2hldiIsImRlcGFydG1lbnQiOiJTREciLCJkaXN0aW5ndWlzaGVkTmFtZSI6IkNOPVRpbXVyIE1hbHlzaGV2LE9VPVNPRlRXQVJFIERFVkVMT1BNRU5UIEdST1VQIChTREcpLE9VPUlORk9STUFUSU9OIFNZU1RFTVMgU1VQUE9SVCBTRUNUSU9OIChJU1NTKSxPVT1SdXNzaWFuIERpZ2l0YWwgQ2VudGVyIChSREMpLE9VPVVzZXJzLE9VPUhNTVIsREM9bG9jYWwsREM9aG1tcixEQz1ydSIsImdyb3VwcyI6W119fQ.8zHWPMtpsGqx8TtEkW2rtit4CqzXFaAFWEy8Nhd-p0w",
#     "is_expired": false,
#     "iat": 1782824210,
#     "exp": 1782867410,
#     "ttl": 12
# }

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
        self.assets_admin: Optional[bool] = payload.get("assets_admin")

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
        return datetime.now().timestamp() > self.exp

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
            "assets_admin": self.assets_admin,
            "permissions": self.permissions,
            "last_ip": self.last_ip,
            "last_time": self.last_time,
            "is_expired": self.is_expired,
            "iat": self.iat,
            "exp": self.exp,
            "ttl": (self.exp-self.iat) / 3600
        }