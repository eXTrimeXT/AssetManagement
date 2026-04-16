from pydantic import BaseModel, ConfigDict, Field
from datetime import date
from typing import Optional

class AssetUpdate(BaseModel):
    """Схема для обновления актива (все поля опциональны)"""

    name: Optional[str] = Field(None, min_length=1, max_length=150)
    inventory_id: Optional[str] = Field(None, min_length=1, max_length=50)
    serial_number: Optional[str] = Field(None, min_length=1, max_length=100)
    asset_type_id: Optional[int] = None
    asset_status: Optional[str] = Field(None, min_length=1, max_length=100)
    type_domain: Optional[str] = Field(None, max_length=100)
    affixed_inventory_id: Optional[bool] = None
    info_storage_location: Optional[str] = Field(None, max_length=200)
    location_id: Optional[int] = Field(None, description="ID локации из справочника Locations")
    passwork: Optional[str] = Field(None, max_length=200)
    date_issue: Optional[date] = None
    date_purchasing: Optional[date] = None
    comment: Optional[str] = None
    parent_id: Optional[int] = None
    prepared_by: Optional[int] = Field(None)
    checked_by: Optional[int] = Field(None)
    deleted_at: Optional[date] = None
    software_id: Optional[int] = None
    price: Optional[int] = Field(None, ge=0, description="Стоимость приобретения")

    manufacturer_id: Optional[int] = Field(None, description="ID производителя")
    vendor_id: Optional[int] = Field(None, description="ID поставщика")

    model_config = ConfigDict(
        json_schema_extra={
        "example": {
            "price": 12345
        }
    })