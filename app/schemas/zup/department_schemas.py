from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
from typing import Optional, List


class DepartmentBase(BaseModel):
    guid: str = Field(..., max_length=36)
    name: str = Field(..., max_length=200)
    name_en: Optional[str] = Field(None, max_length=200)
    short_name: Optional[str] = Field(None, max_length=100)
    creation_date: Optional[date] = None
    closure_date: Optional[date] = None
    parent_guid: Optional[str] = Field(None, max_length=36)


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    name_en: Optional[str] = Field(None, max_length=200)
    short_name: Optional[str] = Field(None, max_length=100)
    creation_date: Optional[date] = None
    closure_date: Optional[date] = None
    parent_guid: Optional[str] = Field(None, max_length=36)


class DepartmentResponse(DepartmentBase):
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_active: bool = True
    hierarchy_path: Optional[List[str]] = None

    # Вложенный parent — тот же DepartmentResponse (без рекурсии дальше)
    parent: Optional["DepartmentParentResponse"] = None

    model_config = ConfigDict(from_attributes=True)

class DepartmentParentResponse(BaseModel):
    """Схема для parent департамента (без вложенного parent)"""
    guid: str
    name: str
    name_en: Optional[str] = None
    short_name: Optional[str] = None
    creation_date: Optional[date] = None
    closure_date: Optional[date] = None
    parent_guid: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)