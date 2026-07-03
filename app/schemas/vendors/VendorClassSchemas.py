from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional


class VendorClassBase(BaseModel):
    name: Optional[str] = None


class VendorClassCreate(VendorClassBase):
    pass


class VendorClassUpdate(BaseModel):
    name: Optional[str] = None


class VendorClassResponse(VendorClassBase):
    class_id: int
    created_at: datetime
    created_by: str

    model_config = ConfigDict(from_attributes=True)


class VendorClassShortResponse(BaseModel):
    class_id: int
    name: str
    created_by: str

    model_config = ConfigDict(from_attributes=True)