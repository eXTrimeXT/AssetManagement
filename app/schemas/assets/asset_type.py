from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class AssetTypeBase(BaseModel):
    name: str
    en_name: str


class AssetTypeCreate(AssetTypeBase):
    pass


class AssetTypeUpdate(BaseModel):
    name: Optional[str] = None
    en_name: Optional[str] = None


class AssetTypeResponse(AssetTypeBase):
    asset_type_id: int
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)