from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
from typing import Optional


class AssetAssignmentCreate(BaseModel):
    """Создание привязки — asset_id в теле запроса"""
    asset_id: int = Field(..., description="ID актива")
    employee_id: str = Field(..., max_length=20, description="Табельный номер сотрудника")
    comment: Optional[str] = Field(None, max_length=500, description="Комментарий")


class AssetAssignmentResponse(BaseModel):
    """Плоский ответ — без вложенностей"""
    id: int
    asset_id: int
    employee_id: str
    start_date: date
    end_date: Optional[date] = None
    assigned_by: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssetUserResponse(BaseModel):
    """Пользователь, привязанный к активу (для поля users в AssetResponse)"""
    employee_id: str
    start_date: date
    end_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)