from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

class AssetClassBase(BaseModel):
    class_name: str = Field(..., min_length=2, max_length=100)
    class_type_id: int
    description: Optional[str] = None

class AssetClassCreate(AssetClassBase):
    created_by: int # ID пользователя, создавшего запись

class AssetClassUpdate(BaseModel):
    class_name: Optional[str] = Field(None, min_length=2, max_length=100)
    class_type_id: Optional[int] = None
    description: Optional[str] = None
    updated_by: Optional[int] = None

class AssetClassResponse(AssetClassBase):
    class_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)