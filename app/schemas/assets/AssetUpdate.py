from pydantic import BaseModel, ConfigDict, Field
from datetime import date
from typing import Optional

class AssetUpdate(BaseModel):
    """Схема для обновления актива (все поля опциональны)"""

    name: Optional[str] = Field(None, min_length=1, max_length=150)
    inventory_id: Optional[str] = Field(None, min_length=1, max_length=50)
    serial_number: Optional[str] = Field(None, min_length=1, max_length=100)
    type_id: Optional[int] = None
    asset_status: Optional[str] = Field(None, min_length=1, max_length=100)
    type_domain: Optional[str] = Field(None, max_length=100)
    affixed_inventory_id: Optional[bool] = None
    info_storage_location: Optional[str] = Field(None, max_length=200)
    location: Optional[str] = Field(None, max_length=150)
    passwork: Optional[str] = Field(None, max_length=200)
    date_issue: Optional[date] = None
    date_purchasing: Optional[date] = None
    comment: Optional[str] = None
    parent_id: Optional[int] = None
    source: Optional[str] = Field(None, max_length=100)
    prepared_by: Optional[str] = Field(None, max_length=100)
    checked_by: Optional[str] = Field(None, max_length=100)
    deleted_at: Optional[date] = None
    # software_id: Optional[int] = Field(None, max_length=100)
    software_id: Optional[int] = None

    model_config = ConfigDict(
        json_schema_extra={
        "example": {
            "name": "Ноутбук Dell Latitude (обновлено)",
            "location": "Кабинет 405",
            "asset_status": "Выдан"
        }
    })