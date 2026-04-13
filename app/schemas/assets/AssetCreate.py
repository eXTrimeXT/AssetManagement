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
    location_id: Optional[int] = Field(None, description="ID локации из справочника Locations")
    passwork: Optional[str] = Field(None, max_length=200, description="Пароль/ключ")
    date_issue: Optional[date] = Field(None, description="Дата выдачи")
    date_purchasing: Optional[date] = Field(None, description="Дата покупки")
    comment: Optional[str] = Field(None, description="Комментарий")

    # Комплектация (родительский актив)
    parent_id: Optional[int] = Field(None, description="ID родительского актива (комплектация)")
    software_id: Optional[int] = Field(None, description="ID программного обеспечения")

    # Новые поля
    seller: Optional[str] = Field(None, max_length=100, description="Продавец/Поставщик")
    price: Optional[int] = Field(None, ge=0, description="Стоимость приобретения")

    # Служебные
    source: Optional[str] = Field(None, max_length=100)
    prepared_by: Optional[str] = Field(None, max_length=100)
    checked_by: Optional[str] = Field(None, max_length=100)


    model_config = ConfigDict(
        json_schema_extra={
        "example": {
            "name": "имя",
            "inventory_id": "инвентарный номер",
            "serial_number": "серийный номер",
            "type_id": 10,
            "asset_status": "Приемка",
            "seller": "Продавец",
            "price": 0,
            "type_domain": "тип домена",
            "affixed_inventory_id": True,
            "info_storage_location": "Место хранения информации об активе",
            "location": "местоположение актива",
            "passwork": "admin123",
            "date_issue": "2026-04-01",
            "date_purchasing": "2026-03-15",
            "comment": "Комментарий",
            "parent_id": None,
            "source": "Источник поступления",
            "prepared_by": "Ответственный за документы",
            "checked_by": "Контроль документов",
            "software_id": None
        }
    })