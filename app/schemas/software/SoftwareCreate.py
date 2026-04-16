from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

class SoftwareCreate(BaseModel):
    """Схема для создания записи о ПО"""

    # Офисное ПО
    office_type: Optional[str] = Field(None, max_length=100, description="Тип офисного ПО")
    office_key: Optional[str] = Field(None, max_length=100, description="Ключ лицензии офиса")

    # Операционная система
    os_type: Optional[str] = Field(None, max_length=100, description="Тип ОС")
    os_key: Optional[str] = Field(None, max_length=100, description="Ключ лицензии ОС")

    # Удалённое управление
    remote_control: Optional[str] = Field(default=None, max_length=150, description="ПО удалённого управления")

    # Права доступа
    admin_permission: bool = Field(default=False, description="Админ права")

    # Установка
    who_installed: Optional[int] = Field(default=None)
    installed_at: Optional[datetime] = Field(default=None, description="Дата установки")

    # Комментарий
    comment: Optional[str] = Field(None, description="Комментарий")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "office_type": "Microsoft Office 365",
                "office_key": "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX",
                "os_type": "Windows 11 Pro",
                "os_key": "YYYYY-YYYYY-YYYYY-YYYYY-YYYYY",
                "remote_control": "TeamViewer 15",
                "admin_permission": False,
                "who_installed": None,
                "installed_at": "2026-04-01T10:00:00",
                "comment": "Стандартный пакет ПО"
            }
        }
    )