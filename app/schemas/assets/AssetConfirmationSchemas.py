from pydantic import BaseModel, Field, model_validator
from typing import Optional, Literal

class CreateConfirmationRequest(BaseModel):
    asset_id: Optional[int] = Field(None, description="ID актива (локальный)")
    material_id: Optional[str] = Field(None, description="Material ID (из SAP)")
    employee_id: Optional[str] = Field(None, description="Табельный номер сотрудника (для массового запроса)")
    comment: Optional[str] = Field(None, description="Комментарий к запросу")

    @model_validator(mode='after')
    def check_at_least_one(self):
        if not self.asset_id and not self.material_id and not self.employee_id:
            raise ValueError("Необходимо указать asset_id, material_id или employee_id")
        return self

class ConfirmAssetRequest(BaseModel):
    asset_id: Optional[int] = Field(None, description="ID актива (если не используется QR)")
    qr_data: Optional[str] = Field(None, description="Данные из QR-кода (JSON или строка с инвентарным/серийным номером)")
    status: Literal["confirmed", "not_found", "damaged"] = Field(..., description="Результат проверки")
    comment: Optional[str] = Field(None, description="Комментарий (обязателен при not_found или damaged)")