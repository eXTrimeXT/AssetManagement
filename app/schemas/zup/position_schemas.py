from pydantic import BaseModel, ConfigDict, Field
from datetime import date
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

class PositionResponse(BaseModel):
    name: str = Field(..., max_length=200)
    name_en: Optional[str] = Field(None, max_length=200)
    model_config = ConfigDict(from_attributes=True)