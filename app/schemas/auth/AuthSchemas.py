from pydantic import BaseModel
from typing import Optional, List, Dict

class TokenRequest(BaseModel):
    token: str

class UserInfoResponse(BaseModel):
    login: str
    email: Optional[str]
    fullname: Optional[str]
    department: Optional[str]
    distinguished_name: Optional[str]
    groups: List[str]
    permissions: Dict[str, Dict[str, bool]]  # {"computer": {"read": true, "write": false}, ...}
    last_ip: Optional[str]
    last_time: Optional[str]