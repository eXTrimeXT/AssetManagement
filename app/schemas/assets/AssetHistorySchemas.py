from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class AssetHistoryResponse(BaseModel):
    id: int
    asset_id: int
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by: str
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)
