import math
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

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
    get_inventorization_discrepancies,
    delete_inventorization_session,
    export_inventory_session_to_excel
)
from app.services.auth.auth_service import require_authorized_user
from app.schemas.PaginationResponse import PaginatedResponse

router_inventorization = APIRouter(prefix="/inventorization", tags=["Assets Inventorization"])

@router_inventorization.get("/sessions/", response_model=List[InventorizationSessionResponse])
async def get_sessions(
        skip: int = 0,
        limit: int = 50,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    return await get_inventory_sessions_list(db, skip, limit)

@router_inventorization.get(
    "/sessions/{session_id}/items/",
    response_model=PaginatedResponse[InventorizationItemResponse]
)
async def get_session_items(
        session_id: int,
        page: int = Query(1, ge=1, description="Номер страницы (начинается с 1)"),
        page_size: int = Query(50, ge=1, le=200, description="Размер страницы"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получить список элементов инвентаризации сессии с пагинацией."""

    # Получаем данные и общее количество из CRUD
    items, total = await get_inventory_items_by_session_id(db, session_id, page, page_size)

    # Рассчитываем метаданные пагинации
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse(
        items=list(items),
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )

@router_inventorization.post("/sessions/", response_model=InventorizationSessionResponse)
async def start_session(
        data: InventorizationSessionCreate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    return await create_inventory_session(
        db=db,
        asset_type_id=data.asset_type_id,
        department_codes=data.department_codes,
        creator_employee_id=current_user.employee_id,
        start_date=data.start_date,
        end_date=data.end_date
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
    success = await check_inventory_item(
        db=db,
        session_id=session_id,
        asset_id=data.asset_id,
        checked_by=current_user.employee_id,
        quantity_fact=data.quantity_fact
    )
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

@router_inventorization.delete("/sessions/{session_id}", status_code=status.HTTP_200_OK)
async def delete_status(
        session_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    db_status = await delete_inventorization_session(db, session_id)
    if not db_status:
        raise HTTPException(status_code=404, detail="Сессия инвентаризации не найдена")
    return {"message": "success"}

@router_inventorization.get(
    "/sessions/{session_id}/export/excel",
    summary="Экспорт сессии инвентаризации в Excel"
)
async def export_session_to_excel(
        session_id: int,
        db: AsyncSession = Depends(get_db),
        # current_user=Depends(require_authorized_user)
):
    """Скачать сессию инвентаризации в формате Excel."""
    try:
        return await export_inventory_session_to_excel(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))