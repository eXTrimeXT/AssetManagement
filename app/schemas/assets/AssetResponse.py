from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
from typing import Optional

# Импорт всех необходимых вложенных схем
from app.schemas.locations.LocationResponse import LocationResponse
from app.schemas.asset_types.AssetTypesSchemas import AssetTypeResponse
from app.schemas.users.UserResponse import UserResponse
from app.schemas.software.SoftwareResponse import SoftwareResponse
from app.schemas.vendors.VendorSchemas import VendorResponse

class AssetBase(BaseModel):
    """Базовые поля актива (простые типы)"""
    name: str
    inventory_id: str
    serial_number: str
    asset_status: str
    type_domain: Optional[str] = None
    affixed_inventory_id: Optional[bool] = None
    info_storage_location: Optional[str] = None
    # passwork: Optional[str] = None
    date_issue: Optional[date] = None
    date_purchasing: Optional[date] = None
    comment: Optional[str] = None

    # ID связей (оставляем для удобства, если клиенту нужны только ID)
    asset_type_id: int
    location_id: Optional[int] = None
    parent_id: Optional[int] = None
    software_id: Optional[int] = None
    prepared_by: Optional[int] = None
    checked_by: Optional[int] = None
    manufacturer_id: Optional[int] = None
    vendor_id: Optional[int] = None

class AssetResponse(AssetBase):
    """
    Полная схема ответа с вложенными объектами.
    Соответствует требуемой структуре JSON.
    """
    asset_id: int
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # --- Вложенные объекты ---

    # Тип актива
    asset_type: Optional[AssetTypeResponse] = None

    # Локация
    location_obj: Optional[LocationResponse] = None

    # Пользователи (Подготовил / Проверил)
    # Используем полную схему UserResponse, так как в примере много полей
    preparer: Optional[UserResponse] = Field(default=None)
    checker: Optional[UserResponse] = Field(default=None)

    # ПО
    software: Optional[SoftwareResponse] = Field(default=None)

    # Производитель и Поставщик (Вендоры)
    manufacturer: Optional[VendorResponse] = Field(default=None)
    vendor: Optional[VendorResponse] = Field(default=None)

    model_config = ConfigDict(
        from_attributes=True,
    )


class AssetShortResponse(BaseModel):
    """Краткая схема для списков"""
    asset_id: int
    name: str
    inventory_id: str
    serial_number: str
    asset_status: str
    asset_type_id: int
    location_id: Optional[int] = None
    parent_id: Optional[int] = None
    software_id: Optional[int] = None
    manufacturer_id: Optional[int] = None
    vendor_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)