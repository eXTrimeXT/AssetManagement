from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional


class ManagerBase(BaseModel):
    id: str = Field(..., max_length=100)
    guid_employee: str = Field(..., max_length=100)
    guid_manager: str = Field(..., max_length=100)


class ManagerCreate(ManagerBase):
    pass


class ManagerResponse(ManagerBase):
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)