from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.AssetType import AssetType
from app.schemas.asset_types.AssetTypeCreate import AssetTypeCreate
from app.schemas.asset_types.AssetTypeUpdate import AssetTypeUpdate
from typing import Sequence

