# app/schemas/assets/AssetExcel.py
from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional

class AssetExcelRow(BaseModel):
    """
    Схема одной строки для ИМПОРТА актива из Excel.
    Поля сгруппированы по логическим категориям для удобства отображения в Excel.
    """

    # === Категория 1: Основная информация (Обязательно) ===
    inventory_id: str = Field(..., description="Инвентарный номер (Уникальный)")
    serial_number: str = Field(..., description="Серийный номер")
    name: str = Field(..., description="Наименование актива")
    asset_type_name: str = Field(..., description="Тип актива (Название из справочника, напр. 'Ноутбук')")
    asset_status: str = Field("Приемка", description="Статус (Приемка, На складе, Выдан...)")

    # === Категория 2: Местоположение (Поиск по названию города/адреса) ===
    location_country: Optional[str] = Field(None, description="Страна")
    location_city: Optional[str] = Field(None, description="Город")
    location_address: Optional[str] = Field(None, description="Адрес (Улица, дом)")
    location_room: Optional[str] = Field(None, description="Помещение/Кабинет")
    location_floor: Optional[str] = Field(None, description="Этаж")

    # === Категория 3: Детали актива ===
    type_domain: Optional[str] = Field(None, description="Домен")
    passwork: Optional[str] = Field(None, description="Пароль/ключ")
    date_issue: Optional[date] = Field(None, description="Дата выдачи (ГГГГ-ММ-ДД)")
    date_purchasing: Optional[date] = Field(None, description="Дата покупки (ГГГГ-ММ-ДД)")
    price: Optional[int] = Field(None, description="Стоимость")
    comment: Optional[str] = Field(None, description="Комментарий")
    affixed_inventory_id: Optional[bool] = Field(False, description="Инв. номер наклеен (Да/Нет)")

    # === Категория 4: Вендоры (Производитель / Поставщик) ===
    # Поиск по названию вендора в таблице vendors
    manufacturer_name: Optional[str] = Field(None, description="Производитель (Название из справочника Vendors)")
    vendor_name: Optional[str] = Field(None, description="Поставщик (Название из справочника Vendors)")

    # === Категория 5: Ответственные лица ===
    # Поиск по ФИО или Email в таблице users
    prepared_by_name: Optional[str] = Field(None, description="Подготовил (ФИО пользователя)")
    checked_by_name: Optional[str] = Field(None, description="Проверил (ФИО пользователя)")

    # === Категория 6: ПО и Комплектация ===
    software_os_type: Optional[str] = Field(None, description="ОС (Название из справочника Software)")
    parent_inventory_id: Optional[str] = Field(None, description="Инвентарный номер родителя (для комплектации)")