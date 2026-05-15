from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, date
from typing import Optional

from app.schemas.assets.AssetResponse import AssetResponse
from app.schemas.catalog.ModelSchemas import AssetModelResponse
from app.schemas.users.UserResponse import UserResponse

class AssetCatalogBase(BaseModel):
    class_id: int
    model_id: int
    asset_id: int
    owner_id: Optional[int] = None
    warranty_end_date: Optional[date] = None

class AssetCatalogCreate(AssetCatalogBase):
    created_by: int

class AssetCatalogUpdate(BaseModel):
    owner_id: Optional[int] = None
    warranty_end_date: Optional[date] = None
    class_id: Optional[int] = None
    model_id: Optional[int] = None

class AssetCatalogResponse(AssetCatalogBase):
    catalog_id: int
    created_at: datetime

    # --- Вложенные объекты вместо ID ---

    # Актив (полный объект со всеми связями: тип, локация, юзеры, вендоры, ПО)
    asset: Optional[AssetResponse] = Field(default=None, alias="asset")

    # Модель оборудования (полный объект со связями: класс, юзеры)
    model: Optional[AssetModelResponse] = Field(default=None, alias="model")

    # Владелец актива (Пользователь)
    owner: Optional[UserResponse] = Field(default=None, alias="owner")

    # Создатель записи в каталоге (Пользователь)
    creator: Optional[UserResponse] = Field(default=None, alias="creator")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True # Позволяет мапить атрибуты модели SQLAlchemy на алиасы полей схемы
    )
    model_config = ConfigDict(from_attributes=True)