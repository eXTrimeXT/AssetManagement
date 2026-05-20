from pydantic import BaseModel
from typing import Optional, List, Any, Dict


class TokenRequest(BaseModel):
    token: str


class UserInfoResponse(BaseModel):
    login: str
    email: Optional[str]
    fullname: Optional[str]
    department: Optional[str]
    distinguished_name: Optional[str]
    groups: List[str]
    permissions: List[Dict[str, Any]]
    role: Optional[str]
    last_ip: Optional[str]
    last_time: Optional[str]