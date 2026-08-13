from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Any


class AuditLogResponse(BaseModel):
    id: Optional[int] = None
    user_login: Optional[str] = None
    action: Optional[str] = None
    entity: Optional[str] = None
    entity_id: Optional[int] = None
    request_data: Optional[Any] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)