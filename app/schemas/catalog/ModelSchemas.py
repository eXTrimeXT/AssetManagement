from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

from app.schemas.catalog.ClassSchemas import AssetClassResponse # Полная схема класса с вложениями
from app.schemas.users.UserResponse import UserResponse # Полная схема пользователя

class AssetModelBase(BaseModel):
    model_name: str = Field(..., min_length=2, max_length=150)
    class_id: int
    description: Optional[str] = None
    is_active: bool = True
    is_serial_required: bool = True

class AssetModelCreate(AssetModelBase):
    created_by: int

class AssetModelUpdate(BaseModel):
    model_name: Optional[str] = None
    class_id: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_serial_required: Optional[bool] = None
    updated_by: Optional[int] = None

class AssetModelResponse(AssetModelBase):
    model_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Вложенные объекты

    # Класс оборудования (полный объект со всеми его связями)
    asset_class: Optional[AssetClassResponse] = Field(default=None)

    # Пользователи (Создатель и Обновляющий саму модель)
    creator: Optional[UserResponse] = Field(default=None, alias="creator")
    updater: Optional[UserResponse] = Field(default=None, alias="updater")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)