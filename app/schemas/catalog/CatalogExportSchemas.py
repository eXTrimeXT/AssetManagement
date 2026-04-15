from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import Optional


class CatalogExportRow(BaseModel):
    """Схема одной строки для экспорта каталога в Excel"""
    # ID записи
    catalog_id: int

    # Информация о классе оборудования
    class_name: str
    class_description: Optional[str] = None

    # Информация о модели оборудования
    model_name: str
    model_description: Optional[str] = None
    model_is_active: bool
    model_is_serial_required: bool

    # Информация об активе
    asset_inventory_id: str
    asset_serial_number: str
    asset_name: str
    asset_status: str
    asset_type_domain: Optional[str] = None
    asset_affixed_inventory_id: Optional[bool] = None
    asset_info_storage_location: Optional[str] = None
    asset_passwork: Optional[str] = None
    asset_date_issue: Optional[date] = None
    asset_date_purchasing: Optional[date] = None
    asset_comment: Optional[str] = None
    asset_source: Optional[str] = None
    asset_seller: Optional[str] = None
    asset_price: Optional[int] = None

    # Владелец
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    owner_department: Optional[str] = None

    # Склад
    warehouse_name: Optional[str] = None
    warehouse_location_city: Optional[str] = None
    warehouse_location_address: Optional[str] = None

    # Гарантия
    warranty_end_date: Optional[date] = None

    # Аудит
    created_at: datetime
    created_by_name: Optional[str] = None
    created_by_email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)