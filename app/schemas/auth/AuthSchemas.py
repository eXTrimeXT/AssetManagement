from pydantic import BaseModel
from typing import Optional, List, Dict

class TokenRequest(BaseModel):
    token: str

class UserInfoResponse(BaseModel):
    login: str
    email: Optional[str]
    fullname: Optional[str]
    distinguished_name: Optional[str] = None
    department: Optional[str] = None
    groups: List[str] = None
    permissions: Dict[str, Dict[str, bool]]  # {"computer": {"read": true, "write": false}, ...}
    permission_departments: List[PermissionDepartments] = None
    assets_admin: Optional[bool]
    last_ip: Optional[str]
    last_time: Optional[str]
    token: Optional[str] = None
    is_expired: Optional[bool] = None
    iat: Optional[int] = None
    exp: Optional[int] = None
    ttl: Optional[int] = None

class LoginRequest(BaseModel):
    login: str
    password: str

class PermissionDepartments(BaseModel):
    name_group: Optional[str] = None
    read: Optional[bool] = None
    write: Optional[bool] = None
    department: Optional[str] = None
    department_code: Optional[str] = None