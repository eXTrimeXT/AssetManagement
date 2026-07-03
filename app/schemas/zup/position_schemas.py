from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
from typing import Optional


class PositionBase(BaseModel):
    guid: str = Field(..., max_length=36)
    name: str = Field(..., max_length=200)
    name_en: Optional[str] = Field(None, max_length=200)
    creation_date: Optional[date] = None
    expiration_date: Optional[date] = None


class PositionCreate(PositionBase):
    pass


class PositionUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    name_en: Optional[str] = Field(None, max_length=200)
    creation_date: Optional[date] = None
    expiration_date: Optional[date] = None


class PositionResponse(PositionBase):
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)