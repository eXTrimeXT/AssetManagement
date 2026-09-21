# from pydantic import BaseModel, model_validator
# from typing import Optional
#
# class SapAssetCreateRequest(BaseModel):
#     inventory_id: str
#     name: str
#     serial_number: Optional[str] = None
#     asset_type_id: int
#     model_id: Optional[int] = None
#     asset_status_id: Optional[int] = 9  # актуальный ID статуса "На складе" из вашей БД
#     quantity: int = 1
#
# class AssetTransferRequest(BaseModel):
#     asset_id: Optional[int] = None
#     sap_asset: Optional[SapAssetCreateRequest] = None
#     target_employee_id: str
#     assignment_type: str = "user"  # "user" или "responsible"
#     comment: Optional[str] = None
#
#     @model_validator(mode='after')
#     def check_asset_source(self):
#         if not self.asset_id and not self.sap_asset:
#             raise ValueError("Необходимо указать либо asset_id, либо данные sap_asset")
#         if self.asset_id and self.sap_asset:
#             raise ValueError("Можно указать только один источник актива: asset_id или sap_asset")
#         if self.assignment_type not in ["user", "responsible"]:
#             raise ValueError("assignment_type должен быть 'user' или 'responsible'")
#         return self
#
# class TransferActionRequest(BaseModel):
#     action: str  # "accept" или "decline"
#     comment: Optional[str] = None
#
#     @model_validator(mode='after')
#     def validate_action(self):
#         if self.action not in ["accept", "decline"]:
#             raise ValueError("Действие должно быть 'accept' или 'decline'")
#         return self

from pydantic import BaseModel, model_validator, ConfigDict
from typing import Optional
from datetime import datetime

class AssetTransferRequest(BaseModel):
    asset_id: Optional[int] = None
    material_id: Optional[str] = None  # передаем только ID из SAP
    target_employee_id: str
    assignment_type: str = "user"  # "user" или "responsible"
    comment: Optional[str] = None

    @model_validator(mode='after')
    def check_asset_source(self):
        if not self.asset_id and not self.material_id:
            raise ValueError("Необходимо указать либо asset_id, либо sap_material_id")
        if self.asset_id and self.material_id:
            raise ValueError("Можно указать только один источник актива: asset_id или sap_material_id")
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

# === СХЕМЫ ОТВЕТА ===

class AssetInfoResponse(BaseModel):
    """Информация об активе"""
    asset_id: int
    inventory_id: str
    name: str
    serial_number: Optional[str] = None
    asset_type_id: Optional[int] = None
    model_id: Optional[int] = None
    source: str  # "local" или "sap"

    model_config = ConfigDict(from_attributes=True)

class EmployeeInfoResponse(BaseModel):
    """Краткая информация о сотруднике"""
    employee_id: str
    full_name: Optional[str] = None

class NotificationInfoResponse(BaseModel):
    """Информация о созданном уведомлении"""
    notification_id: int
    event_type: str
    event_type_ru: str
    status: str
    created_at: datetime

class AssetTransferResponse(BaseModel):
    """Ответ на запрос передачи актива"""
    message: str
    action: str  # "transfer_initiated"

    # Информация об уведомлении
    notification: NotificationInfoResponse

    # Информация об активе
    asset: AssetInfoResponse

    # Участники передачи
    initiator: EmployeeInfoResponse
    target_employee: EmployeeInfoResponse

    # Детали передачи
    assignment_type: str
    assignment_type_ru: str
    comment: Optional[str] = None
    created_at: datetime

class AssetTransferRespondResponse(BaseModel):
    """Ответ на принятие/отклонение передачи"""
    message: str
    action: str  # "accept" или "decline"

    # Информация об уведомлении
    notification: NotificationInfoResponse

    # Информация об активе
    asset: AssetInfoResponse

    # Участники передачи
    initiator: EmployeeInfoResponse
    responder: EmployeeInfoResponse

    # Детали
    assignment_type: str
    assignment_type_ru: str
    comment: Optional[str] = None
    responded_at: datetime

    # Дополнительная информация при принятии
    new_assignment_id: Optional[int] = None
    previous_assignment_closed: bool = False