from pydantic import BaseModel, Field
from typing import Optional

class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    abbreviation: Optional[str] = Field(None, min_length=1, max_length=50)

    class Config:
        from_attributes = True