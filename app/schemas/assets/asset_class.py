from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from app.schemas.assets.asset_type import AssetTypeResponse


class AssetClassBase(BaseModel):
    class_name: str
    description: Optional[str] = None
    asset_type_id: int


class AssetClassCreate(AssetClassBase):
    pass


class AssetClassUpdate(BaseModel):
    class_name: Optional[str] = None
    description: Optional[str] = None
    asset_type_id: Optional[int] = None


class AssetClassResponse(AssetClassBase):
    class_id: int
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    asset_type: Optional[AssetTypeResponse] = None

    model_config = ConfigDict(from_attributes=True)