from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional
from app.schemas.users.UserResponse import UserShortResponse
from app.schemas.companies.CompanySchemas import CompanyShortResponse, CompanyResponse
from app.schemas.vendors.VendorClassSchemas import VendorClassShortResponse


class VendorBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Название вендора/поставщика")
    vendor_class_id: int = Field(..., description="ID класса (справочник vendor_classes)")
    company_id: Optional[int] = Field(None, description="ID компании (опционально)")


class VendorCreate(VendorBase):
    created_by: int = Field(..., description="ID пользователя, создавшего запись")


class VendorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    vendor_class_id: Optional[int] = None
    company_id: Optional[int] = None


class VendorResponse(VendorBase):
    vendor_id: int
    created_at: datetime
    created_by: Optional[int] = None

    # Вложенные объекты для удобного отображения
    vendor_class: VendorClassShortResponse
    company: Optional[CompanyResponse] = None
    creator: Optional[UserShortResponse] = None

    model_config = ConfigDict(from_attributes=True)


class VendorShortResponse(BaseModel):
    vendor_id: int
    name: str
    vendor_class_id: int
    company_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)