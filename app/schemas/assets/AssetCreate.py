from pydantic import BaseModel, ConfigDict, Field
from datetime import date
from typing import Optional

class AssetCreate(BaseModel):
    """Схема для создания нового актива"""

    # Обязательные поля
    name: str = Field(..., min_length=1, max_length=150, description="Имя актива")
    inventory_id: str = Field(..., min_length=1, max_length=50, description="Инвентарный номер")
    serial_number: Optional[str] = Field(..., max_length=100, description="Серийный номер")
    model_id: Optional[int] = Field(None, description="Модель актива (ссылка на справочник)")

    # Статус
    asset_status: str = Field(default="Приемка", max_length=50, description="Статус актива")

    # Опциональные поля
    type_domain: Optional[str] = Field(None, max_length=100, description="Тип домена")
    affixed_inventory_id: Optional[bool] = Field(False, description="Инвентарный номер наклеен?")
    info_storage_location: Optional[str] = Field(None, max_length=200, description="Место хранения информации")
    warehouse_id: Optional[int] = Field(None, description="ID склада из справочника Warehouse")
    date_issue: Optional[date] = Field(None, description="Дата выдачи")
    date_purchasing: Optional[date] = Field(None, description="Дата покупки")
    comment: Optional[str] = Field(None, description="Комментарий")

    # Комплектация (родительский актив)
    parent_id: Optional[int] = Field(None, description="ID родительского актива (комплектация)")
    software_id: Optional[int] = Field(None, description="ID программного обеспечения")

    # Производители / Поставщики
    manufacturer_id: Optional[int] = Field(None, description="ID производителя (из таблицы vendors)")
    vendor_id: Optional[int] = Field(None, description="ID поставщика (из таблицы vendors)")

    price: Optional[int] = Field(None, ge=0, description="Стоимость приобретения")

    # Служебные
    prepared_by: Optional[int] = Field(None)
    checked_by: Optional[int] = Field(None)


    model_config = ConfigDict(
        json_schema_extra={
        "example": {
            "name": "имя",
            "inventory_id": "инвентарный номер",
            "serial_number": "серийный номер",
            "model_id": 1,
            "asset_status": "Приемка",
            "price": 0,
            "date_issue": "2026-04-01",
            "date_purchasing": "2026-03-15",
            "parent_id": None,
            "manufacturer_id": 1,
            "vendor_id": 1,
            "prepared_by": 1,
            "checked_by": 1,
            "software_id": None
        }
    })

class AssetCreateRequest(BaseModel):
    name: Optional[str]
    inventory_id: Optional[str]
    serial_number: Optional[str]
    asset_status: Optional[str] = "Приемка"
    comment: Optional[str] = None
    model_name: Optional[str] = None
    type_asset_en_name: Optional[str] = None
    type_asset_name: Optional[str] = None
    warehouse_name: Optional[str] = None
    parent_name: Optional[str] = None
    software_office_type: Optional[str] = None
    manufacturer_name: Optional[str] = None
    vendor_name: Optional[str] = None

    class Config:
        from_attributes = True