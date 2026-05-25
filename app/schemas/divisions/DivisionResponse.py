from pydantic import BaseModel, ConfigDict
from typing import List

class DivisionResponse(BaseModel):
    id: int
    name: str
    abbreviation: str
    department_id: int
    model_config = ConfigDict(from_attributes=True)

class DivisionShortResponse(BaseModel):
    id: int
    name: str
    abbreviation: str
    model_config = ConfigDict(from_attributes=True)

class GroupShortForDivision(BaseModel):
    id: int
    name: str
    abbreviation: str
    model_config = ConfigDict(from_attributes=True)

class DivisionWithGroupsResponse(DivisionResponse):
    groups: List[GroupShortForDivision] = []
    model_config = ConfigDict(from_attributes=True)