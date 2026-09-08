from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.services.auth.auth_service import require_authorized_user
from app.services.sap_sync_service.sync_sap_assets import sync_sap_assets

router_from_sap = APIRouter(prefix="/assets", tags=["Assets"])


@router_from_sap.post("/sync-from-sap")
async def sync_assets_from_sap(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    result = await sync_sap_assets(db)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message"))

    return result