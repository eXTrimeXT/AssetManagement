from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

from app.schemas.asset_types.AssetTypesSchemas import AssetTypeResponse
from app.schemas.users.UserResponse import UserResponse


class AssetClassBase(BaseModel):
    class_name: str = Field(..., min_length=2, max_length=100)
    class_type_id: int
    description: Optional[str] = None

class AssetClassCreate(AssetClassBase):
    created_by: Optional[str] = None # табельник пользователя, создавшего запись

class AssetClassUpdate(BaseModel):
    class_name: Optional[str] = Field(None, min_length=2, max_length=100)
    class_type_id: Optional[int] = None
    description: Optional[str] = None
    updated_by: Optional[str] = None

class AssetClassResponse(AssetClassBase):
    class_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Вложенные объекты вместо простых ID
    # Pydantic возьмет данные из атрибутов модели 'asset_type', 'creator', 'updater'
    asset_type: Optional[AssetTypeResponse] = Field(default=None, alias="asset_type")
    created_by_user: Optional[UserResponse] = Field(default=None, alias="creator")
    updated_by_user: Optional[UserResponse] = Field(default=None, alias="updater")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)