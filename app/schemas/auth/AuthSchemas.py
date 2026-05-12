from pydantic import BaseModel
from typing import Optional, List

class TokenRequest(BaseModel):
    token: str


class UserInfoResponse(BaseModel):
    login: str
    email: Optional[str]
    fullname: Optional[str]
    department: Optional[str]
    groups: List[str]
    last_ip: Optional[str]
    last_time: Optional[str]