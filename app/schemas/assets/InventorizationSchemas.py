from pydantic import BaseModel
from datetime import datetime

class InventorizationSessionCreate(BaseModel):
    asset_type_id: int

class InventorizationSessionResponse(BaseModel):
    session_id: int
    asset_type_id: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

class InventorizationItemResponse(BaseModel):
    inventorization_id: int
    session_id: int
    asset_id: int
    is_checked: bool

    model_config = {"from_attributes": True}

class CheckItemRequest(BaseModel):
    asset_id: int