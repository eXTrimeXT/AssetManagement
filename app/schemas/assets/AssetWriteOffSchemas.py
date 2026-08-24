from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, date
from typing import Optional, List
from enum import Enum


class WriteOffStatusEnum(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class WriteOffTypeEnum(str, Enum):
    BROKEN = "broken"
    LOST = "lost"
    OBSOLETE = "obsolete"
    SOLD = "sold"
    OTHER = "other"


class WriteOffRequest(BaseModel):
    """Запрос на списание актива"""
    reason: str = Field(..., max_length=1000)
    write_off_type: WriteOffTypeEnum = WriteOffTypeEnum.OTHER


class WriteOffRejectRequest(BaseModel):
    """Отклонение заявки на списание"""
    reject_reason: str = Field(..., max_length=1000)


class WriteOffResponse(BaseModel):
    write_off_id: int
    asset_id: int
    reason: str
    write_off_type: str
    requested_by: str
    requested_at: datetime
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    reject_reason: Optional[str] = None
    status: str

    # Данные об активе
    asset_name: Optional[str] = None
    asset_inventory_id: Optional[str] = None

    # ФИО инициатора
    requester_full_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class WriteOffListResponse(BaseModel):
    items: List[WriteOffResponse]
    total: int
    page: int
    page_size: int