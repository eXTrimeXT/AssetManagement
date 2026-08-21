from datetime import datetime
from typing import Optional, Dict, Any, List, Literal

# {
#     "login": "gw07015370",
#     "email": "Timur.Malyshev@hmmr.ru",
#     "fullname": "Timur Malyshev",
#     "distinguished_name": "CN=Timur Malyshev,OU=SOFTWARE DEVELOPMENT GROUP (SDG),OU=INFORMATION SYSTEMS SUPPORT SECTION (ISSS),OU=Russian Digital Center (RDC),OU=Users,OU=HMMR,DC=local,DC=hmmr,DC=ru",
#     "department": "RDC",
#     "groups": [],
#     "permissions": {
#         "computer": {
#             "read": false,
#             "write": false
#         },
#         "mes_equipment": {
#             "read": true,
#             "write": true
#         },
#         "supplies": {
#             "read": true,
#             "write": true
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
#         "AssetsMU": {
#             "read": true,
#             "write": true
#         },
#         "android_data": {
#             "read": true,
#             "write": false
#         }
#     },
#     "assets_admin": false,
#     "last_ip": "10.168.135.30",
#     "last_time": "13:02:53 19.08.2026",
#     "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3ODcyODk1MTMsImV4cCI6MTc4NzMzMjcxMywibG9naW4iOiJndzA3MDE1MzcwIiwibGFzdF9pcCI6IjEwLjE2OC4xMzUuMzAiLCJsYXN0X3RpbWUiOiIxMzowMjo1MyAxOS4wOC4yMDI2IiwiZGVwYXJ0bWVudCI6IlJEQyIsInBlcm1pc3Npb25zIjpbeyJuYW1lX2dyb3VwIjoiY29tcHV0ZXIiLCJyZWFkIjpmYWxzZSwid3JpdGUiOmZhbHNlfSx7Im5hbWVfZ3JvdXAiOiJtZXNfZXF1aXBtZW50IiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6InN1cHBsaWVzIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6InBvd2VyX2FkYXB0ZXIiLCJyZWFkIjp0cnVlLCJ3cml0ZSI6dHJ1ZX0seyJuYW1lX2dyb3VwIjoiZGF0YV9jb2xsZWN0aW9uX2VxdWlwbWVudCIsInJlYWQiOnRydWUsIndyaXRlIjp0cnVlfSx7Im5hbWVfZ3JvdXAiOiJBY2Nlc3NvcmllcyIsInJlYWQiOnRydWUsIndyaXRlIjp0cnVlfSx7Im5hbWVfZ3JvdXAiOiJuZXR3b3JrX2VxdWlwbWVudCIsInJlYWQiOnRydWUsIndyaXRlIjp0cnVlfSx7Im5hbWVfZ3JvdXAiOiJwcmludGluZ19lcXVpcG1lbnQiLCJyZWFkIjp0cnVlLCJ3cml0ZSI6dHJ1ZX0seyJuYW1lX2dyb3VwIjoic2VydmVyX2hhcmR3YXJlIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6InVzZXJzIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6IkFzc2V0c01VIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6ImFuZHJvaWRfZGF0YSIsInJlYWQiOnRydWUsIndyaXRlIjpmYWxzZX1dLCJhc3NldHNfaXNfYWRtaW4iOnRydWUsInVzZXJfZGF0YSI6eyJlbWFpbCI6IlRpbXVyLk1hbHlzaGV2QGhtbXIucnUiLCJmdWxsbmFtZSI6IlRpbXVyIE1hbHlzaGV2IiwiZGVwYXJ0bWVudCI6IlJEQyIsImRpc3Rpbmd1aXNoZWROYW1lIjoiQ049VGltdXIgTWFseXNoZXYsT1U9U09GVFdBUkUgREVWRUxPUE1FTlQgR1JPVVAgKFNERyksT1U9SU5GT1JNQVRJT04gU1lTVEVNUyBTVVBQT1JUIFNFQ1RJT04gKElTU1MpLE9VPVJ1c3NpYW4gRGlnaXRhbCBDZW50ZXIgKFJEQyksT1U9VXNlcnMsT1U9SE1NUixEQz1sb2NhbCxEQz1obW1yLERDPXJ1IiwiZ3JvdXBzIjpbXX19.mPXHgKKmuSDuUi78Atva9DKEMGpAbQiLNU8pDOG0-Kw",
#     "is_expired": false,
#     "iat": 1787289513,
#     "exp": 1787332713,
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
        self.assets_admin: Optional[bool] = payload.get("assets_admin", False)

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
            except Exception:
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
            "ttl": (self.exp - self.iat) / 3600
        }