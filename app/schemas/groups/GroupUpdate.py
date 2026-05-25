from pydantic import BaseModel, Field
from typing import Optional

class GroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    abbreviation: Optional[str] = Field(None, min_length=1, max_length=50)
    division_id: Optional[int] = Field(None, gt=0)

    class Config:
        from_attributes = True