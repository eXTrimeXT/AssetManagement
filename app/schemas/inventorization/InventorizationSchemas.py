from pydantic import BaseModel, ConfigDict, model_validator
from datetime import datetime
from typing import Optional, List

class InventorizationSessionCreate(BaseModel):
    asset_type_id: Optional[int] = None
    department_codes: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class InventorizationItemResponse(BaseModel):
    inventorization_id: int
    session_id: int
    asset_id: Optional[int] = None
    material_id: Optional[str] = None
    asset_name: str
    is_checked: bool

    serial_number: Optional[str] = None
    inventory_id: Optional[str] = None

    quantity: Optional[int] = None
    quantity_fact: Optional[int] = None

    checked_by: Optional[str] = None
    checked_by_full_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class InventorizationSessionResponse(BaseModel):
    session_id: Optional[int] = None
    asset_type_id: Optional[int] = None
    department_codes: Optional[str] = None
    asset_type_name: Optional[str] = None
    asset_type_en_name: Optional[str] = None
    status: Optional[str] = None
    created_at: datetime
    # items: List[InventorizationItemResponse] = []
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class CheckItemRequest(BaseModel):
    asset_id: Optional[int] = None
    material_id: Optional[str] = None
    quantity_fact: Optional[int] = None

    @model_validator(mode='after')
    def check_either_id(self) -> 'CheckItemRequest':
        if self.asset_id is None and self.material_id is None:
            raise ValueError("Необходимо указать либо asset_id, либо material_id")
        return self


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
    asset_type_id: Optional[int] = None
    asset_type_name: Optional[str] = None
    department_codes: Optional[str] = None
    status: Optional[str] = None
    created_at: datetime
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

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