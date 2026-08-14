from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import Optional

class AssetWriteOffCreate(BaseModel):
    asset_id: int
    reason: str
    reason_description: Optional[str] = None
    act_number: str
    act_date: date
    disposal_method: Optional[str] = None
    notes: Optional[str] = None

class AssetWriteOffResponse(BaseModel):
    id: int
    asset_id: int
    reason: str
    reason_description: Optional[str] = None
    act_number: str
    act_date: date
    disposal_method: Optional[str] = None
    initiated_by: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)