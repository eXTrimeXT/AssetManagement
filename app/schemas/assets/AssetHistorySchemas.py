from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List

class AssetHistoryResponse(BaseModel):
    id: int
    asset_id: Optional[int] = None
    action_type: Optional[str] = None
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by: Optional[str] = None
    changed_at: Optional[datetime] = None
    comment: Optional[str] = None
    session_id: Optional[str] = None

    # ФИО изменившего
    changer_full_name_ru: Optional[str] = None
    changer_full_name_en: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AssetHistoryGroupedResponse(BaseModel):
    """Группировка изменений по session_id"""
    session_id: Optional[str] = None
    asset_id: Optional[int] = None
    changed_by: Optional[int] = None
    changer_full_name_ru: Optional[str] = None
    changed_at: Optional[datetime] = None
    changes: List[AssetHistoryResponse] = None
    comment: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AssetHistoryStatsResponse(BaseModel):
    """Статистика по истории изменений"""
    total_changes: int
    changes_today: int
    changes_this_week: int
    changes_this_month: int
    most_active_users: List[dict]  # [{employee_id, full_name, count}]
    most_changed_assets: List[dict]  # [{asset_id, name, count}]
    action_type_breakdown: dict  # {action_type: count}