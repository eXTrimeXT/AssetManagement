from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from datetime import date, datetime
from app.schemas.zup.DepartmentSchemas import WorkplaceResponse
from app.schemas.zup.PositionSchemas import PositionResponse

class EmployeeBase(BaseModel):
    """Базовая схема сотрудника"""
    guid: str = Field(..., max_length=36)
    guid_person: Optional[str] = Field(None, max_length=36)
    employee_id: str = Field(..., max_length=20)
    last_name: Optional[str] = Field(None, max_length=100)
    first_name: Optional[str] = Field(None, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    last_name_en: Optional[str] = Field(None, max_length=100)
    first_name_en: Optional[str] = Field(None, max_length=100)
    middle_name_en: Optional[str] = Field(None, max_length=100)
    birth_date: Optional[date] = None
    employment_date: Optional[date] = None
    dismissal_date: Optional[date] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    comment: Optional[str] = Field(None, max_length=1000)
    position_guid: Optional[str] = Field(None, max_length=36)
    department_guid: Optional[str] = Field(None, max_length=36)

class EmployeeCreate(EmployeeBase):
    """Схема создания сотрудника"""
    pass

class EmployeeCommentUpdate(BaseModel):
    """Схема для обновления только комментария сотрудника"""
    comment: Optional[str] = Field(None, max_length=1000)

class EmployeeUpdate(BaseModel):
    """Схема обновления сотрудника (все поля опциональные)"""
    guid_person: Optional[str] = Field(None, max_length=36)
    last_name: Optional[str] = Field(None, max_length=100)
    first_name: Optional[str] = Field(None, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    last_name_en: Optional[str] = Field(None, max_length=100)
    first_name_en: Optional[str] = Field(None, max_length=100)
    middle_name_en: Optional[str] = Field(None, max_length=100)
    birth_date: Optional[date] = None
    employment_date: Optional[date] = None
    dismissal_date: Optional[date] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    comment: Optional[str] = Field(None, max_length=1000)
    position_guid: Optional[str] = Field(None, max_length=36)
    department_guid: Optional[str] = Field(None, max_length=36)

class EmployeeResponse(EmployeeBase):
    """Полная схема ответа"""
    created_at: datetime
    updated_at: Optional[datetime] = None
    # Вычисляемые поля
    full_name_ru: Optional[str] = None
    full_name_en: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class EmployeePersonalResponse(EmployeeBase):
    """Полная схема ответа"""
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Вычисляемые поля
    full_name_ru: Optional[str] = None
    full_name_en: Optional[str] = None

    # === НОВЫЕ ПОЛЯ: иерархия и должность ===
    society: Optional[WorkplaceResponse] = None
    department: Optional[WorkplaceResponse] = None
    division: Optional[WorkplaceResponse] = None
    group: Optional[WorkplaceResponse] = None
    position: Optional[PositionResponse] = None

    model_config = ConfigDict(from_attributes=True)

class EmployeeShortResponse(BaseModel):
    """Краткая схема для списков"""
    guid: str
    employee_id: str
    full_name_ru: Optional[str] = None
    full_name_en: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    comment: Optional[str] = Field(None, max_length=1000)
    society: Optional[WorkplaceResponse] = None
    department: Optional[WorkplaceResponse] = None
    division: Optional[WorkplaceResponse] = None
    group: Optional[WorkplaceResponse] = None
    position: Optional[PositionResponse] = None
    model_config = ConfigDict(from_attributes=True)

