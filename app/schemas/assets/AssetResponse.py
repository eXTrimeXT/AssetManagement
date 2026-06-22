from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
from typing import Optional

# Импорт всех необходимых вложенных схем
from app.schemas.warehouses.WarehouseResponse import WarehouseResponse
from app.schemas.users.UserResponse import UserResponse
from app.schemas.software.SoftwareResponse import SoftwareResponse
from app.schemas.vendors.VendorSchemas import VendorResponse
from app.schemas.catalog.ModelSchemas import AssetModelResponse


class AssetBase(BaseModel):
    """Базовые поля актива (простые типы)"""
    name: str
    inventory_id: str
    serial_number: Optional[str]
    asset_status: str
    type_domain: Optional[str] = None
    affixed_inventory_id: Optional[bool] = None
    info_storage_location: Optional[str] = None
    date_issue: Optional[date] = None
    date_purchasing: Optional[date] = None
    comment: Optional[str] = None

    # ID связей
    model_id: Optional[int]
    warehouse_id: Optional[int] = None
    parent_id: Optional[int] = None
    software_id: Optional[int] = None
    prepared_by: Optional[int] = None
    checked_by: Optional[int] = None
    manufacturer_id: Optional[int] = None
    vendor_id: Optional[int] = None

class AssetWorkshopInfo(BaseModel):
    """
    Информация о цехе в составе актива.
    """
    model_config = ConfigDict(from_attributes=True)

    workshop_id: int
    name: str
    code: str

class AssetResponse(AssetBase):
    """
    Полная схема ответа с вложенными объектами.
    """
    asset_id: int
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # --- Вложенные объекты ---
    model: Optional[AssetModelResponse] = None

    # СКЛАД
    warehouse_obj: Optional[WarehouseResponse] = None

    # === НОВОЕ ПОЛЕ ===
    workshop_id: Optional[int] = None
    workshop: Optional[AssetWorkshopInfo] = None


    # Пользователи
    preparer: Optional[UserResponse] = Field(default=None)
    checker: Optional[UserResponse] = Field(default=None)

    # ПО
    software: Optional[SoftwareResponse] = Field(default=None)

    # Производитель и Поставщик
    manufacturer: Optional[VendorResponse] = Field(default=None)
    vendor: Optional[VendorResponse] = Field(default=None)

    model_config = ConfigDict(from_attributes=True)

class AssetShortResponse(BaseModel):
    """Краткая схема для списков"""
    asset_id: int
    name: str
    inventory_id: str
    serial_number: Optional[str]
    asset_status: str

    model_id: Optional[int]

    type_asset: Optional[str] = None

    warehouse_id: Optional[int] = None

    parent_id: Optional[int] = None

    software_id: Optional[int] = None

    manufacturer_id: Optional[int] = None

    vendor_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)