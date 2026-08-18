from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List

from app.schemas.assets import AssetShortResponse, AssetResponse


class NotificationBase(BaseModel):
    employee_id: str
    asset_id: int
    notification_checked: bool = False


class NotificationResponse(NotificationBase):
    notification_id: int
    created_at: datetime

    asset: Optional[AssetShortResponse] = None  # новое поле

    model_config = ConfigDict(from_attributes=True)


class NotificationCheckRequest(BaseModel):
    notification_checked: bool = True


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    page: int
    page_size: int