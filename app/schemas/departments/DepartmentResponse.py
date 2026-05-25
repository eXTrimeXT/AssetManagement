from pydantic import BaseModel, ConfigDict
from typing import List

class DepartmentResponse(BaseModel):
    id: int
    name: str
    abbreviation: str
    model_config = ConfigDict(from_attributes=True)

class DepartmentShortResponse(BaseModel):
    id: int
    name: str
    abbreviation: str
    model_config = ConfigDict(from_attributes=True)

class GroupShortForDivision(BaseModel):
    id: int
    name: str
    abbreviation: str
    model_config = ConfigDict(from_attributes=True)

class DivisionWithGroupsForDepartment(BaseModel):
    id: int
    name: str
    abbreviation: str
    groups: List[GroupShortForDivision] = []
    model_config = ConfigDict(from_attributes=True)

class DepartmentWithDivisionsAndGroupsResponse(DepartmentResponse):
    divisions: List[DivisionWithGroupsForDepartment] = []
    model_config = ConfigDict(from_attributes=True)