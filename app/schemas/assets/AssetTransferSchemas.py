from pydantic import BaseModel, model_validator
from typing import Optional

class SapAssetCreateRequest(BaseModel):
    inventory_id: str
    name: str
    serial_number: Optional[str] = None
    asset_type_id: int
    model_id: Optional[int] = None
    asset_status_id: Optional[int] = 9  # актуальный ID статуса "На складе" из вашей БД
    quantity: int = 1

class AssetTransferRequest(BaseModel):
    asset_id: Optional[int] = None
    sap_asset: Optional[SapAssetCreateRequest] = None
    target_employee_id: str
    assignment_type: str = "user"  # "user" или "responsible"
    comment: Optional[str] = None

    @model_validator(mode='after')
    def check_asset_source(self):
        if not self.asset_id and not self.sap_asset:
            raise ValueError("Необходимо указать либо asset_id, либо данные sap_asset")
        if self.asset_id and self.sap_asset:
            raise ValueError("Можно указать только один источник актива: asset_id или sap_asset")
        if self.assignment_type not in ["user", "responsible"]:
            raise ValueError("assignment_type должен быть 'user' или 'responsible'")
        return self

class TransferActionRequest(BaseModel):
    action: str  # "accept" или "decline"
    comment: Optional[str] = None

    @model_validator(mode='after')
    def validate_action(self):
        if self.action not in ["accept", "decline"]:
            raise ValueError("Действие должно быть 'accept' или 'decline'")
        return self