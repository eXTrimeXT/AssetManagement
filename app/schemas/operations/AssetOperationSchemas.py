from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Dict, Any
from app.schemas.users.UserResponse import UserShortResponse

class AssetOperationBase(BaseModel):
    asset_id: int
    operation_type: str
    comment: Optional[str] = None

class AssetOperationCreate(AssetOperationBase):
    performed_by: Optional[int] = None
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None

class AssetOperationResponse(AssetOperationBase):
    id: int
    timestamp: datetime
    performed_by: Optional[int] = None
    performer: Optional[UserShortResponse] = None
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)