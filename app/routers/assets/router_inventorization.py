from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.schemas.assets.InventorizationSchemas import InventorizationSessionCreate, InventorizationSessionResponse, \
    CheckItemRequest, InventorizationItemResponse
from app.database.assets.crud_inventorization import create_inventory_session, check_inventory_item, \
    complete_inventory_session, get_inventory_sessions_list, get_inventory_items_by_session_id

router_inventorization = APIRouter(prefix="/inventorization", tags=["Assets Inventorization"])

@router_inventorization.get("/sessions/", response_model=Sequence[InventorizationSessionResponse])
async def get_sessions(skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)):
    return await get_inventory_sessions_list(db, skip, limit)

@router_inventorization.get("/sessions/{session_id}/items/", response_model=Sequence[InventorizationItemResponse])
async def get_session_items(session_id: int, db: AsyncSession = Depends(get_db)):
    return await get_inventory_items_by_session_id(db, session_id)

@router_inventorization.post("/sessions/", response_model=InventorizationSessionResponse)
async def start_session(data: InventorizationSessionCreate, db: AsyncSession = Depends(get_db)):
    return await create_inventory_session(db, data.asset_type_id)

@router_inventorization.post("/sessions/{session_id}/check")
async def check_item(session_id: int, data: CheckItemRequest, db: AsyncSession = Depends(get_db)):
    success = await check_inventory_item(db, session_id, data.asset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Актив не найден в этой сессии инвентаризации")
    return {"message": "Актив отмечен как проверенный"}

@router_inventorization.post("/sessions/{session_id}/complete", response_model=InventorizationSessionResponse)
async def complete_session(session_id: int, db: AsyncSession = Depends(get_db)):
    session = await complete_inventory_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    return session

