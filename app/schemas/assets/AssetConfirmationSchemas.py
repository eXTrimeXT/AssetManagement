from datetime import datetime
from pydantic import BaseModel, Field, model_validator
from typing import Optional, Literal, List

class CreateConfirmationRequest(BaseModel):
    asset_id: Optional[int] = Field(None, description="ID актива (локальный)")
    employee_id: Optional[str] = Field(None, description="Табельный номер сотрудника (для массового запроса)")
    comment: Optional[str] = Field(None, description="Комментарий к запросу")

    @model_validator(mode='after')
    def check_at_least_one(self):
        if not self.asset_id and not self.employee_id:
            raise ValueError("Необходимо указать asset_id, material_id или employee_id")
        return self

class ConfirmAssetRequest(BaseModel):
    # asset_id теперь строго обязателен, так как мы всегда его знаем при подтверждении
    asset_id: int = Field(..., description="ID актива (обязательно)")

    # Поля для сверки. Если переданы, они должны строго совпадать с БД.
    inventory_id: Optional[str] = Field(None, description="Инвентарный номер для сверки")
    serial_number: Optional[str] = Field(None, description="Серийный номер для сверки")

    status: Literal["confirmed", "not_found", "damaged"] = Field(..., description="Результат проверки")
    comment: Optional[str] = Field(None, description="Комментарий (обязателен при not_found или damaged)")

class AssetConfirmationResponse(BaseModel):
    id: int
    asset_id: int
    asset_name: Optional[str] = None
    employee_id: str
    employee_full_name: Optional[str] = None
    requested_by: Optional[str] = None
    requested_full_name: Optional[str] = None
    status: str
    status_ru: str
    comment: Optional[str] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}