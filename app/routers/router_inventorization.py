from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.schemas.inventorization.InventorizationSchemas import (
    InventorizationSessionCreate,
    InventorizationSessionResponse,
    CheckItemRequest,
    InventorizationItemResponse,
    InventorizationReportResponse,
    InventorizationDiscrepanciesResponse,
)
from app.database.inventorization.crud_inventorization import (
    create_inventory_session,
    check_inventory_item,
    complete_inventory_session,
    get_inventory_sessions_list,
    get_inventory_items_by_session_id,
    get_inventory_session_by_id,
    get_inventorization_report,
    get_inventorization_discrepancies
)
from app.services.auth.auth_service import require_authorized_user

router_inventorization = APIRouter(prefix="/inventorization", tags=["Assets Inventorization"])

@router_inventorization.get("/sessions/", response_model=List[InventorizationSessionResponse])
async def get_sessions(
        skip: int = 0,
        limit: int = 50,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    return await get_inventory_sessions_list(db, skip, limit)

@router_inventorization.get("/sessions/{session_id}/items/", response_model=List[InventorizationItemResponse])
async def get_session_items(
        session_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    return await get_inventory_items_by_session_id(db, session_id)

@router_inventorization.post("/sessions/", response_model=InventorizationSessionResponse)
async def start_session(
        data: InventorizationSessionCreate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    return await create_inventory_session(
        db,
        data.asset_type_id,
        current_user.employee_id,
        data.start_date,
        data.end_date
    )

@router_inventorization.post("/sessions/{session_id}/check")
async def check_item(
        session_id: int,
        data: CheckItemRequest,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    # === ПРОВЕРКА: сессия не должна быть completed ===
    session = await get_inventory_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия инвентаризации не найдена")
    if session.status == "completed":
        raise HTTPException(
            status_code=400,
            detail="Сессия уже завершена. Изменять items нельзя."
        )
    if data.quantity_fact is not None and data.quantity_fact < 0:
        raise HTTPException(
            status_code=400,
            detail="Количество не может быть меньше 0"
        )
    success = await check_inventory_item(db, session_id, data.asset_id, data.quantity_fact)
    if not success:
        raise HTTPException(status_code=404, detail="Актив не найден в этой сессии инвентаризации")
    return {"message": "success"}

@router_inventorization.post("/sessions/{session_id}/complete", response_model=InventorizationSessionResponse)
async def complete_session(
        session_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    # === ПРОВЕРКА: нельзя завершить уже завершенную сессию ===
    session = await get_inventory_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия инвентаризации не найдена")
    if session.status == "completed":
        raise HTTPException(
            status_code=400,
            detail="Сессия уже завершена."
        )
    session = await complete_inventory_session(db, session_id, updated_by=current_user.employee_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    return session


@router_inventorization.get(
    "/sessions/{session_id}/report",
    response_model=InventorizationReportResponse,
    summary="Получить отчёт по сессии инвентаризации"
)
async def get_session_report(
        session_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Сводный отчёт: прогресс, расхождения, излишки, недостачи."""
    report = await get_inventorization_report(db, session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Сессия инвентаризации не найдена")
    return report

@router_inventorization.get(
    "/sessions/{session_id}/report/discrepancies",
    response_model=InventorizationDiscrepanciesResponse,
    summary="Получить список расхождений"
)
async def get_session_discrepancies(
        session_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    """Список расхождений: недостачи, излишки, непроверенные."""
    result = await get_inventorization_discrepancies(db, session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Сессия инвентаризации не найдена")
    return result