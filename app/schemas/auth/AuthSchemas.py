from pydantic import BaseModel
from typing import Optional, List, Dict

class TokenRequest(BaseModel):
    token: str

class UserInfoResponse(BaseModel):
    user_id: int
    login: str
    email: Optional[str]
    fullname: Optional[str]
    distinguished_name: Optional[str]
    department: Optional[str]
    groups: List[str]
    permissions: Dict[str, Dict[str, bool]]  # {"computer": {"read": true, "write": false}, ...}
    last_ip: Optional[str]
    last_time: Optional[str]
    token: Optional[str] = None

class LoginRequest(BaseModel):
    login: str
    password: str