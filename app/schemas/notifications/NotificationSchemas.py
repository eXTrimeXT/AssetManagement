from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List


class NotificationBase(BaseModel):
    employee_id: str
    asset_id: int
    notification_checked: bool = False


class NotificationResponse(NotificationBase):
    notification_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedNotificationResponse(BaseModel):
    """Ответ со списком уведомлений и количеством непрочитанных"""
    items: List[NotificationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool
    unchecked_count: int  # количество непрочитанных


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    page: int
    page_size: int