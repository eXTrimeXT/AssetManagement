from pydantic import BaseModel, ConfigDict
from typing import Optional

# Количество активов по статусам
class CountByGroupResponse(BaseModel):
    name: Optional[str]
    count: int
    model_config = ConfigDict(from_attributes=True)