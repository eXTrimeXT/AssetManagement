from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional


class VendorClassBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Название класса (например: Производитель, Поставщик)")


class VendorClassCreate(VendorClassBase):
    pass


class VendorClassUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)


class VendorClassResponse(VendorClassBase):
    vendor_class_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VendorClassShortResponse(BaseModel):
    vendor_class_id: int
    name: str

    model_config = ConfigDict(from_attributes=True)