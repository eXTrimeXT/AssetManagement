from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import date
from typing import Optional

# app/schemas/assets/AssetUpdate.py
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import date
from typing import Optional

class AssetUpdate(BaseModel):
    """Схема для обновления актива (все поля опциональны)"""
    asset_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    inventory_id: Optional[str] = Field(None, min_length=1, max_length=50)
    serial_number: Optional[str] = Field(None, max_length=100)
    model_id: Optional[int] = None
    asset_status: Optional[str] = Field(None, min_length=1, max_length=100)
    type_domain: Optional[str] = Field(None, max_length=100)
    affixed_inventory_id: Optional[bool] = None
    info_storage_location: Optional[str] = Field(None, max_length=200)
    warehouse_id: Optional[int] = Field(None)
    date_issue: Optional[date] = None
    date_purchasing: Optional[date] = None
    comment: Optional[str] = None
    parent_id: Optional[int] = None
    prepared_by: Optional[int] = Field(None)
    checked_by: Optional[int] = Field(None)
    deleted_at: Optional[date] = None
    software_id: Optional[int] = None
    price: Optional[int] = Field(None, ge=0)

    manufacturer_id: Optional[int] = Field(None, description="ID производителя")
    vendor_id: Optional[int] = Field(None, description="ID поставщика")

    # === Поля, которые шлёт фронтенд (игнорируются, но нужны чтобы не ломалось) ===
    model_name: Optional[str] = None
    class_id: Optional[int] = None
    class_name: Optional[str] = None
    asset_type_id: Optional[int] = None
    type_asset_en_name: Optional[str] = None
    type_asset_name: Optional[str] = None
    warehouse_name: Optional[str] = None
    parent_name: Optional[str] = None
    software_office_type: Optional[str] = None
    manufacturer_name: Optional[str] = None
    vendor_name: Optional[str] = None

    @field_validator('*', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """Преобразуем пустые строки в None для всех полей"""
        if isinstance(v, str) and v.strip() == '':
            return None
        return v


    @field_validator('date_issue', 'date_purchasing', 'deleted_at', mode='before')
    @classmethod
    def parse_dates(cls, v):
        if v is None:
            return None
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            try:
                # Пробуем распарсить строку YYYY-MM-DD
                return date.fromisoformat(v)
            except ValueError:
                raise ValueError(f"Неверный формат даты: {v}. Ожидается ГГГГ-ММ-ДД")
        raise ValueError("Неподдерживаемый тип даты")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "price": 12345
            }
        }
    )