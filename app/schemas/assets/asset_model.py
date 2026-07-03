from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from app.schemas.assets.asset_class import AssetClassResponse


class AssetModelBase(BaseModel):
    model_name: str
    description: Optional[str] = None
    class_id: int


class AssetModelCreate(AssetModelBase):
    pass


class AssetModelUpdate(BaseModel):
    model_name: Optional[str] = None
    description: Optional[str] = None
    class_id: Optional[int] = None


class AssetModelResponse(AssetModelBase):
    model_id: int
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    asset_class: Optional[AssetClassResponse] = None

    model_config = ConfigDict(from_attributes=True)