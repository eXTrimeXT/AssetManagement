from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional

class CatalogExcelRow(BaseModel):
    """Схема одной строки для Excel (Человеко-читаемая)"""
    catalog_id: Optional[int] = Field(None, description="ID записи (заполняется при экспорте)")
    class_name: str = Field(..., description="Название класса (напр. 'Ноутбук')")
    model_name: str = Field(..., description="Название модели (напр. 'Lenovo V110')")
    asset_status: str = Field(..., description="Статус актива")
    quantity: Optional[int] = Field(None, description="Количество (только для чтения/отчета)")
    owner_name: Optional[str] = Field(None, description="ФИО владельца")
    warehouse_name: Optional[str] = Field(None, description="Название склада")
    serial_number: Optional[str] = Field(None, description="Серийный номер")
    warranty_end_date: Optional[date] = Field(None, description="Дата окончания гарантии")
    created_at: Optional[datetime] = Field(None, description="Дата создания")
    created_by_name: Optional[str] = Field(None, description="Кто создал (ФИО)")

class CatalogImportRow(BaseModel):
    """Схема для валидации строки перед импортом (без ID)"""
    class_name: str
    model_name: str
    asset_status: str
    owner_name: Optional[str] = None
    warehouse_name: Optional[str] = None
    serial_number: Optional[str] = None
    warranty_end_date: Optional[date] = None
    created_by_name: Optional[str] = None # Обычно берется из текущей сессии пользователя