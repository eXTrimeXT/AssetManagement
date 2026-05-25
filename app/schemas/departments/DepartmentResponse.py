from pydantic import BaseModel, Field
from typing import Optional, List

class DepartmentResponse(BaseModel):
    id: int
    name: str
    abbreviation: str

    class Config:
        from_attributes = True