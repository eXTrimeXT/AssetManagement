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
    """Полная информация о пользователе, привязанном к активу"""
    # Поля из Employee
    guid: str
    guid_person: Optional[str] = None
    employee_id: str
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name_en: Optional[str] = None
    first_name_en: Optional[str] = None
    middle_name_en: Optional[str] = None
    birth_date: Optional[date] = None
    employment_date: Optional[date] = None
    dismissal_date: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    position_guid: Optional[str] = None
    department_guid: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    full_name_ru: Optional[str] = None
    full_name_en: Optional[str] = None

    # Поля из AssetAssignment
    start_date: date
    end_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)