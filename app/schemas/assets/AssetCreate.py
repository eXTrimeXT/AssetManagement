from pydantic import BaseModel, ConfigDict, Field
from datetime import date
from typing import Optional

class AssetCreate(BaseModel):
    """Схема для создания нового актива"""

    # Обязательные поля
    name: str = Field(..., min_length=1, max_length=150, description="Имя актива")
    inventory_id: str = Field(..., min_length=1, max_length=50, description="Инвентарный номер")
    serial_number: str = Field(..., min_length=1, max_length=100, description="Серийный номер")
    type_id: int = Field(..., description="Тип актива (ссылка на справочник)")

    # Статус
    asset_status: str = Field(default="Приемка", max_length=50, description="Статус актива")

    # Опциональные поля
    type_domain: Optional[str] = Field(None, max_length=100, description="Тип домена")
    affixed_inventory_id: Optional[bool] = Field(None, description="Инвентарный номер наклеен?")
    info_storage_location: Optional[str] = Field(None, max_length=200, description="Место хранения информации")
    location: Optional[str] = Field(None, max_length=150, description="Местоположение")
    passwork: Optional[str] = Field(None, max_length=200, description="Пароль/ключ")
    date_issue: Optional[date] = Field(None, description="Дата выдачи")
    date_purchasing: Optional[date] = Field(None, description="Дата покупки")
    comment: Optional[str] = Field(None, description="Комментарий")

    # Комплектация (родительский актив)
    parent_id: Optional[int] = Field(None, description="ID родительского актива (комплектация)")
    software_id: Optional[int] = Field(None, description="ID программного обеспечения")

    # Служебные
    source: Optional[str] = Field(None, max_length=100)
    prepared_by: Optional[str] = Field(None, max_length=100)
    checked_by: Optional[str] = Field(None, max_length=100)


    model_config = ConfigDict(
        json_schema_extra={
        "example": {
            "name": "Ноутбук Dell Latitude",
            "inventory_id": "INV-2026-001",
            "serial_number": "SN123456789",
            "type_id": 10,
            "asset_status": "Приемка",
            "type_domain": "CORP",
            "affixed_inventory_id": True,
            "info_storage_location": "Серверная, шкаф 3",
            "location": "Кабинет 301",
            "passwork": "admin123",
            "date_issue": "2026-04-01",
            "date_purchasing": "2026-03-15",
            "comment": "Рабочая станция бухгалтера",
            "parent_id": None,
            "source": "Закупка",
            "prepared_by": "Иванов И.И.",
            "checked_by": "Петров П.П.",
            "software_id": None
        }
    })