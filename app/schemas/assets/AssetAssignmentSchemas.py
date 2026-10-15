from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
from typing import Optional
from app.schemas.zup import WorkplaceResponse, PositionResponse

class AssetAssignmentCreate(BaseModel):
    """Создание привязки — asset_id в теле запроса"""
    asset_id: int = Field(..., description="ID актива")
    employee_id: str = Field(..., max_length=20, description="Табельный номер сотрудника")
    assignment_type: Optional[str] = Field("user", max_length=20, description="Тип привязки")
    comment: Optional[str] = Field(None, max_length=500, description="Комментарий")
    is_current: bool = Field(False, description="Флаг является ли этот пользователь текущим пользователем")

class AssetAssignmentResponse(BaseModel):
    """Плоский ответ — без вложенностей"""
    id: int
    asset_id: int
    employee_id: str
    start_date: date
    end_date: Optional[date] = None
    assigned_by: Optional[str] = None
    assignment_type: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime
    is_current: bool

    model_config = ConfigDict(from_attributes=True)

class AssetUserFullResponse(BaseModel):
    """Полная информация о пользователе актива с иерархией и должностью"""
    # Базовые поля сотрудника
    guid: str
    employee_id: str
    # last_name: Optional[str] = None
    # first_name: Optional[str] = None
    # middle_name: Optional[str] = None
    # last_name_en: Optional[str] = None
    # first_name_en: Optional[str] = None
    # middle_name_en: Optional[str] = None
    birth_date: Optional[date] = None
    employment_date: Optional[date] = None
    dismissal_date: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    comment: Optional[str] = None
    position_guid: Optional[str] = None
    department_guid: Optional[str] = None

    # Служебные поля
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Вычисляемые поля
    full_name_ru: Optional[str] = None
    full_name_en: Optional[str] = None

    # Иерархия и должность
    society: Optional[WorkplaceResponse] = None
    department: Optional[WorkplaceResponse] = None
    division: Optional[WorkplaceResponse] = None
    group: Optional[WorkplaceResponse] = None
    position: Optional[PositionResponse] = None

    # Поля из AssetAssignment
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    assignment_type: Optional[str] = None
    # is_current: bool

    model_config = ConfigDict(from_attributes=True)