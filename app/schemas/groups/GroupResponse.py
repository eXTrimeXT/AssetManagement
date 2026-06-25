from typing import Optional
from pydantic import BaseModel


class GroupDivisionDepartmentIdsResponse(BaseModel):
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    group_abbreviation: Optional[str] = None

    division_id: Optional[int] = None
    division_name: Optional[str] = None
    division_abbreviation: Optional[str] = None

    department_id: Optional[int] = None
    department_name: Optional[str] = None
    department_abbreviation: Optional[str] = None

