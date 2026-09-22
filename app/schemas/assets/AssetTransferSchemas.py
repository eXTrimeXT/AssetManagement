from pydantic import BaseModel, model_validator, ConfigDict
from typing import Optional, Literal
from datetime import datetime

class AssetTransferRequest(BaseModel):
    asset_id: Optional[int] = None
    material_id: Optional[str] = None
    target_employee_id: str
    assignment_type: Literal["user", "responsible"] = "user"
    comment: Optional[str] = None

    @model_validator(mode='after')
    def check_asset_source(self):
        if not self.asset_id and not self.material_id:
            raise ValueError("Необходимо указать либо asset_id, либо material_id")
        if self.asset_id and self.asset_id != 0 and self.material_id and self.material_id != "":
            raise ValueError("Можно указать только один источник актива: asset_id или material_id")
        return self

class TransferActionRequest(BaseModel):
    action: Literal["accept", "decline"]
    comment: Optional[str] = None

class AssetInfoResponse(BaseModel):
    asset_id: int
    inventory_id: str
    name: str
    serial_number: Optional[str] = None
    asset_type_id: Optional[int] = None
    model_id: Optional[int] = None
    source: str

    model_config = ConfigDict(from_attributes=True)

class EmployeeInfoResponse(BaseModel):
    employee_id: str
    full_name: Optional[str] = None

class NotificationInfoResponse(BaseModel):
    notification_id: int
    event_type: str
    event_type_ru: str
    status: str
    created_at: datetime

class AssetTransferResponse(BaseModel):
    message: str
    action: str
    transfer_id: int
    notification: NotificationInfoResponse
    asset: AssetInfoResponse
    initiator: EmployeeInfoResponse
    target_employee: EmployeeInfoResponse
    assignment_type: str
    assignment_type_ru: str
    comment: Optional[str] = None
    created_at: datetime

class AssetTransferRespondResponse(BaseModel):
    message: str
    action: str
    transfer_id: int
    notification: NotificationInfoResponse
    asset: AssetInfoResponse
    initiator: EmployeeInfoResponse
    responder: EmployeeInfoResponse
    assignment_type: str
    assignment_type_ru: str
    comment: Optional[str] = None
    responded_at: datetime
    new_assignment_id: Optional[int] = None
    previous_assignment_closed: bool = False

class AssetTransferCancelResponse(BaseModel):
    message: str
    transfer_id: int
    status: str
    cancelled_at: datetime