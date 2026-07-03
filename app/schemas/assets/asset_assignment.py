from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
from typing import Optional
from app.schemas.zup.employee_schemas import EmployeeShortResponse


class AssetAssignmentBase(BaseModel):
    asset_id: int = Field(..., description="ID актива")
    employee_id: str = Field(..., max_length=20, description="Табельный номер сотрудника")
    comment: Optional[str] = Field(None, max_length=500, description="Комментарий")


class AssetAssignmentCreate(BaseModel):
    employee_id: str = Field(..., max_length=20, description="Табельный номер сотрудника")
    comment: Optional[str] = Field(None, max_length=500, description="Комментарий")


class AssetAssignmentResponse(AssetAssignmentBase):
    id: int
    start_date: date
    end_date: Optional[date] = None
    assigned_by: Optional[str] = None
    created_at: datetime

    # Вложенные объекты
    employee: Optional[EmployeeShortResponse] = None
    assigner: Optional[EmployeeShortResponse] = None

    model_config = ConfigDict(from_attributes=True)


class AssetAssignmentShortResponse(BaseModel):
    id: int
    employee_id: str
    start_date: date
    end_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)