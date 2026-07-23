from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class InventorizationSessionCreate(BaseModel):
    asset_type_id: int

class InventorizationItemResponse(BaseModel):
    inventorization_id: int
    session_id: int
    asset_id: int
    asset_name: str
    asset_inventory_id: str
    asset_serial_number: Optional[str]
    is_checked: bool

    model_config = {"from_attributes": True}

class InventorizationSessionResponse(BaseModel):
    session_id: int
    asset_type_id: int
    asset_type_name: str
    asset_type_en_name: str
    status: str
    created_at: datetime
    items: List[InventorizationItemResponse] = []

    model_config = {"from_attributes": True}

class CheckItemRequest(BaseModel):
    asset_id: int