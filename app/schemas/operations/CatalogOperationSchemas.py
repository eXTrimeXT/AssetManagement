from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Dict, Any
from app.schemas.users.UserResponse import UserShortResponse

class CatalogOperationBase(BaseModel):
    catalog_id: int
    operation_type: str
    comment: Optional[str] = None

class CatalogOperationResponse(CatalogOperationBase):
    id: int
    timestamp: datetime
    performed_by: Optional[int] = None
    performer: Optional[UserShortResponse] = None

    # Снимки данных
    asset_inventory_id_snapshot: Optional[str] = None
    model_name_snapshot: Optional[str] = None
    class_name_snapshot: Optional[str] = None

    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)