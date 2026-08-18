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

    # ФИО изменившего
    changer_full_name_ru: Optional[str] = None
    changer_full_name_en: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
