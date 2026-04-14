from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, date
from typing import Optional

class AssetCatalogBase(BaseModel):
    class_id: int
    model_id: int
    asset_id: int
    owner_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    warranty_end_date: Optional[date] = None

class AssetCatalogCreate(AssetCatalogBase):
    created_by: int

class AssetCatalogUpdate(BaseModel):
    owner_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    warranty_end_date: Optional[date] = None
    # Class и Model обычно не меняют у существующего актива, но если нужно:
    # class_id: Optional[int] = None
    # model_id: Optional[int] = None

class AssetCatalogResponse(AssetCatalogBase):
    catalog_id: int
    created_at: datetime
    created_by: Optional[int] = None

    # Вложенные данные для удобства (опционально)
    # model_name: Optional[str] = None
    # asset_inventory_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)