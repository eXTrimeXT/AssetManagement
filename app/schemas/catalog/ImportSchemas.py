from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ClassImportRow(BaseModel):
    """Схема одной строки из Excel для Класса"""
    class_name: str = Field(..., alias="Наименование")
    parent_class_name: Optional[str] = Field(None, alias="Родительский класс")
    description: Optional[str] = Field(None, alias="Описание")
    # Поля аудита игнорируем, так как там строки, а нужны ID пользователей
    # changed_at: Optional[datetime] = Field(None, alias="Когда изменено")
    # changed_by_str: Optional[str] = Field(None, alias="Кем изменено")

    model_config = {"populate_by_name": True}

class ModelImportRow(BaseModel):
    """Схема одной строки из Excel для Модели"""
    model_name: str = Field(..., alias="Наименование")
    class_name: str = Field(..., alias="Класс")
    description: Optional[str] = Field(None, alias="Описание")

    # Обработка булевых значений из Excel (TRUE/FALSE/1/0)
    is_active: bool = Field(True, alias="Активна")
    is_serial_required: bool = Field(False, alias="Серийный номер обязательный")

    model_config = {"populate_by_name": True}