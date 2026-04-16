from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from app.schemas.locations.LocationResponse import LocationResponse


class CompanyBase(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=255, description="Название компании")
    gen_director: Optional[str] = Field(None, max_length=150, description="Генеральный директор (ФИО)")
    phone_number: Optional[str] = Field(None, max_length=50, description="Телефон компании")
    location_id: Optional[int] = Field(None, description="ID локации (адреса) компании")

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(BaseModel):
    company_name: Optional[str] = Field(None, min_length=2, max_length=255)
    gen_director: Optional[str] = Field(None, max_length=150)
    phone_number: Optional[str] = Field(None, max_length=50)
    location_id: Optional[int] = None

class CompanyResponse(CompanyBase):
    company_id: int
    location_obj: Optional[LocationResponse] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class CompanyShortResponse(BaseModel):
    company_id: int
    company_name: str
    phone_number: Optional[str] = None
    location_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)