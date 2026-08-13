from pydantic import BaseModel, ConfigDict
from typing import Optional

# Топ пользователей по активности
class UserActivityResponse(BaseModel):
    user_login: Optional[str]
    change_count: int
    model_config = ConfigDict(from_attributes=True)