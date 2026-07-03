from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
from typing import Optional
from decimal import Decimal


class AssignmentBase(BaseModel):
    id: str = Field(..., max_length=36)
    start_date: date
    end_date: Optional[date] = None
    employee_guid: str = Field(..., max_length=36)
    department_guid: str = Field(..., max_length=36)
    position_guid: str = Field(..., max_length=36)
    fte: Optional[Decimal] = Field(default=1.0, max_digits=5, decimal_places=2)


class AssignmentCreate(AssignmentBase):
    pass


class AssignmentResponse(AssignmentBase):
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_current: bool = True

    model_config = ConfigDict(from_attributes=True)