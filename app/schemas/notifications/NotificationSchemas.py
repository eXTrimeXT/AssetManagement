from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List


class NotificationBase(BaseModel):
    employee_id: str
    asset_id: int
    event_type: str
    initiator_id: Optional[str] = None
    status: str = "unread"


class NotificationResponse(NotificationBase):
    notification_id: int
    responded_at: Optional[datetime] = None
    created_at: datetime

    # Данные об активе
    asset_name: Optional[str] = None
    asset_inventory_id: Optional[str] = None

    # Данные об инициаторе
    initiator_full_name: Optional[str] = None

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
    unchecked_count: int


class NotificationGroupedItem(BaseModel):
    """Группа уведомлений по активу"""
    asset_id: int
    asset_name: Optional[str] = None
    asset_inventory_id: Optional[str] = None
    notifications: List[NotificationResponse]
    total: int
    unread_count: int


class NotificationDeclineResponse(BaseModel):
    message: str
    notification_id: int