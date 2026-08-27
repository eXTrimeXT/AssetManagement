from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List

class InventorizationSessionCreate(BaseModel):
    asset_type_id: int

class InventorizationItemResponse(BaseModel):
    inventorization_id: int
    session_id: int
    asset_id: int
    asset_name: str
    is_checked: bool

    serial_number: Optional[str] = None

    quantity: Optional[int] = None
    quantity_fact: Optional[int] = None

    model_config = {"from_attributes": True}

class InventorizationSessionResponse(BaseModel):
    session_id: int
    asset_type_id: int
    asset_type_name: str
    asset_type_en_name: str
    status: str
    created_at: datetime
    # items: List[InventorizationItemResponse] = []

    model_config = ConfigDict(from_attributes=True)

class CheckItemRequest(BaseModel):
    asset_id: int
    quantity_fact: Optional[int] = None


""" Списание """
class InventorizationItemDiscrepancy(BaseModel):
    """Расхождение по активу"""
    inventorization_id: int
    asset_id: int
    asset_name: str
    serial_number: Optional[str] = None
    quantity: Optional[int] = None
    quantity_fact: Optional[int] = None
    difference: Optional[int] = None  # quantity_fact - quantity, на сколько расхождение?
    discrepancy_type: str  # "missing" | "surplus" | "match" | "not_checked"


class InventorizationReportResponse(BaseModel):
    """Отчёт по сессии инвентаризации"""
    session_id: int
    asset_type_id: int
    asset_type_name: str
    status: str
    created_at: datetime

    # Общая статистика
    total_items: int
    checked_items: int
    unchecked_items: int
    progress_percent: float

    # Расхождения
    matches_count: int       # количество совпало
    discrepancies_count: int # количество отличается
    surplus_count: int       # излишки (факт > учёт)
    missing_count: int       # недостача (факт < учёт)
    not_checked_count: int   # не проверено

    model_config = ConfigDict(from_attributes=True)


class InventorizationDiscrepanciesResponse(BaseModel):
    """Список расхождений сессии"""
    session_id: int
    total_discrepancies: int
    items: List[InventorizationItemDiscrepancy]