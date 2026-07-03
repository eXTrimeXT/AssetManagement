from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List, Optional


class AttendanceData(BaseModel):
    department: str
    total_employees: int
    present_employees: int
    absent_employees: int
    attendance_value: int


class ReportResponse(BaseModel):
    attendance_data: List[AttendanceData]

    model_config = ConfigDict(from_attributes=True)