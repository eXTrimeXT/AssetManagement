from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, date
from typing import Optional
from app.schemas.assets.AssetResponse import AssetResponse
from app.schemas.users.UserResponse import UserResponse

class AssetCatalogBase(BaseModel):
    asset_id: int
    android_id: Optional[str] = None
    owner_id: Optional[int] = None

class AssetCatalogCreate(AssetCatalogBase):
    created_by: int

class AssetCatalogUpdate(BaseModel):
    asset_id: Optional[int] = None
    owner_id: Optional[int] = None
    android_id: Optional[str] = None

class AssetCatalogResponse(AssetCatalogBase):
    catalog_id: int
    created_at: datetime

    # Актив (полный объект со всеми связями: тип, локация, юзеры, вендоры, ПО)
    asset: Optional[AssetResponse] = Field(default=None, alias="asset")
    # Android данные (полный объект)
    android_data_obj: Optional[dict] = Field(default=None, alias="android_data")
    # Владелец актива (Пользователь)
    owner: Optional[UserResponse] = Field(default=None, alias="owner")
    # Создатель записи в каталоге (Пользователь)
    creator: Optional[UserResponse] = Field(default=None, alias="creator")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True # Позволяет мапить атрибуты модели SQLAlchemy на алиасы полей схемы
    )