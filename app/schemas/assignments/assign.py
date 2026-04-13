from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List

# Вложенные схемы для детального вывода
class AssetTypeRef(BaseModel):
    asset_type_id: int
    name: str
    type_id: int
    model_config = ConfigDict(from_attributes=True)

class SoftwareShortRef(BaseModel):
    software_id: int
    office_type: Optional[str] = None
    os_type: Optional[str] = None
    admin_permission: bool
    model_config = ConfigDict(from_attributes=True)

class AssetChildRef(BaseModel):
    asset_id: int
    name: str
    inventory_id: str
    serial_number: str
    asset_status: str
    parent_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

class AssetFullRef(BaseModel):
    asset_id: int
    name: str
    inventory_id: str
    serial_number: str
    asset_status: str
    location: Optional[str] = None
    parent_id: Optional[int] = None
    asset_type: Optional[AssetTypeRef] = None
    software: Optional[SoftwareShortRef] = None
    children: List[AssetChildRef] = []
    model_config = ConfigDict(from_attributes=True)

class AssignmentDetailResponse(BaseModel):
    assign_id: int
    user_id: int
    asset_id: int
    assigned_at: datetime
    returned_at: Optional[datetime] = None
    role: Optional[str] = None
    asset: Optional[AssetFullRef] = None  # Полная инфо об активе
    model_config = ConfigDict(from_attributes=True)

class UserFullInfoResponse(BaseModel):
    user_id: int
    user_tab_id: Optional[str] = None
    owner: str
    email: str
    department: Optional[str] = None
    phone: Optional[str] = None
    assignments: List[AssignmentDetailResponse] = []
    model_config = ConfigDict(from_attributes=True)