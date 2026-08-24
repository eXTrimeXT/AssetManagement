from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List
from enum import Enum


class ActionType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ASSIGN = "assign"
    UNASSIGN = "unassign"
    MOVE = "move"
    STATUS_CHANGE = "status_change"


class AssetHistoryResponse(BaseModel):
    id: int
    asset_id: int
    action_type: str
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by: str
    changed_at: datetime
    comment: Optional[str] = None
    session_id: Optional[str] = None

    # ФИО изменившего
    changer_full_name_ru: Optional[str] = None
    changer_full_name_en: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AssetHistoryGroupedResponse(BaseModel):
    """Группировка изменений по session_id"""
    session_id: str
    asset_id: int
    changed_by: str
    changer_full_name_ru: Optional[str] = None
    changed_at: datetime
    changes: List[AssetHistoryResponse]
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


class AssetHistoryFilterRequest(BaseModel):
    """Фильтры для получения истории"""
    asset_id: Optional[int] = None
    changed_by: Optional[str] = None
    action_type: Optional[ActionType] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    session_id: Optional[str] = None