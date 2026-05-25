from pydantic import BaseModel, Field
from typing import Optional, List
from app.schemas.groups.GroupResponse import GroupShortResponse

class DivisionResponse(BaseModel):
    id: int
    name: str
    abbreviation: str
    department_id: int

    class Config:
        from_attributes = True

class DivisionShortResponse(BaseModel):
    id: int
    name: str
    abbreviation: str

    class Config:
        from_attributes = True