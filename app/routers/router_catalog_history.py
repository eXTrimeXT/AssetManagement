from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.database.connection import get_db
from app.database.crud_catalog_operations import get_catalog_history
from app.schemas.operations.CatalogOperationSchemas import CatalogOperationResponse
from app.service.auth.auth_service import require_authorized_user

router_catalog_history = APIRouter(prefix="/catalog", tags=["Catalog History"], dependencies=[Depends(require_authorized_user)])

@router_catalog_history.get("/items/{catalog_id}/history", response_model=List[CatalogOperationResponse])
async def get_catalog_item_history_endpoint(
        catalog_id: int,
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_db)
):
    """
    Получает историю операций для записи каталога.
    Работает даже если запись была удалена (так как история хранится отдельно).
    """
    # Опционально: можно проверить, существовала ли вообще такая запись,
    # но так как история хранится отдельно, можно сразу отдавать логи.
    history = await get_catalog_history(db, catalog_id, skip, limit)
    return history