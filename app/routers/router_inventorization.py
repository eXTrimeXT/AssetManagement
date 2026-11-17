import math
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.database.connection import get_db
from app.schemas.inventorization.InventorizationSchemas import (
    InventorizationSessionResponse,
    CheckItemRequest,
    InventorizationItemResponse,
    InventorizationReportResponse,
    InventorizationDiscrepanciesResponse,
    InventorizationSessionObj,
)
from app.database.inventorization.crud_inventorization import (
    create_inventory_sessions,
    check_inventory_item,
    complete_inventory_session,
    get_inventory_sessions_list,
    get_inventory_items_by_session_id,
    get_inventory_session_by_id,
    get_inventorization_report,
    get_inventorization_discrepancies,
    delete_inventorization_session,
    export_inventory_session_to_excel,
)
from app.services.auth.auth_service import require_authorized_user
from app.schemas.PaginationResponse import PaginatedResponse

router_inventorization = APIRouter(prefix="/inventorization", tags=["Assets Inventorization"])

@router_inventorization.get(
    "/sessions/",
    response_model=List[InventorizationSessionResponse],
    summary="Получить список сессий инвентаризации / Get Inventory Sessions List",
    description=(
            "RU: Возвращает список всех сессий инвентаризации с поддержкой пагинации "
            "через параметры `skip` и `limit`. По умолчанию возвращается до 50 записей. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns a list of all inventory sessions with pagination support "
            "via `skip` and `limit` parameters. By default, up to 50 records are returned. "
            "User authorization is required."
    )
)
async def get_sessions(
        skip: int = 0,
        limit: int = 50,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    return await get_inventory_sessions_list(db, skip, limit)


@router_inventorization.get(
    "/sessions/{session_id}/items/",
    response_model=PaginatedResponse[InventorizationItemResponse],
    summary="Получить позиции сессии инвентаризации / Get Inventory Session Items",
    description=(
            "RU: Возвращает пагинированный список позиций (активов) указанной сессии инвентаризации. "
            "Поддерживает фильтрацию по `material_id`, `name`, `serial_number`, `inventory_id` "
            "и параметр `is_checked` для отображения только проверенных или непроверенных активов. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns a paginated list of items (assets) for the specified inventory session. "
            "Supports filtering by `material_id`, `name`, `serial_number`, `inventory_id`, "
            "and the `is_checked` parameter to display only checked or unchecked assets. "
            "User authorization is required."
    )
)
async def get_session_items(
        session_id: int,
        page: int = Query(1, ge=1, description="Номер страницы (начинается с 1)"),
        page_size: int = Query(50, ge=1, le=200, description="Размер страницы"),
        material_id: Optional[str] = Query(None, description="Поиск по номеру основного средства"),
        name: Optional[str] = Query(None, description="Поиск по имени"),
        serial_number: Optional[str] = Query(None, description="Поиск по серийному номеру"),
        inventory_id: Optional[str] = Query(None, description="Поиск по инвентарному номеру"),
        is_checked: Optional[Literal["all", "checked", "not_checked"]] = Query("all", description="Фильтр по проверенным активам"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    items, total = await get_inventory_items_by_session_id(
        db=db,
        session_id=session_id,
        page=page,
        page_size=page_size,
        material_id=material_id,
        name=name,
        serial_number=serial_number,
        inventory_id=inventory_id,
        is_checked=is_checked
    )
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


@router_inventorization.post(
    "/sessions/",
    response_model=List[InventorizationSessionResponse],
    summary="Создать сессию инвентаризации / Create Inventory Session",
    description=(
            "RU: Создает одну или несколько сессий инвентаризации на основе указанных параметров: "
            "типов активов (`asset_type_ids`), кодов подразделений (`department_codes`), "
            "классов материалов (`material_classes`) и диапазона дат. "
            "Если по указанным параметрам не найдено ни одного актива — возвращается ошибка 400. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Creates one or more inventory sessions based on the specified parameters: "
            "asset types (`asset_type_ids`), department codes (`department_codes`), "
            "material classes (`material_classes`), and date range. "
            "If no assets are found for the specified parameters, a 400 error is returned. "
            "User authorization is required."
    )
)
async def start_session(
        data: InventorizationSessionObj,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    if not data.obj:
        raise HTTPException(status_code=400, detail="Тело запроса пустое")

    sessions = await create_inventory_sessions(
        db=db,
        asset_type_ids=data.obj.asset_type_ids,
        department_codes=data.obj.department_codes,
        material_classes=data.obj.material_classes,
        creator_employee_id=current_user.employee_id,
        start_date=data.obj.start_date,
        end_date=data.obj.end_date
    )

    if not sessions:
        raise HTTPException(
            status_code=400,
            detail="По указанным параметрам не найдено ни одного актива. Сессии не созданы."
        )

    return sessions


@router_inventorization.post(
    "/sessions/{session_id}/check",
    summary="Отметить актив как проверенный / Mark Asset as Checked",
    description=(
            "RU: Отмечает актив как проверенный в рамках указанной сессии инвентаризации. "
            "Актив идентифицируется по `asset_id` или `material_id`. "
            "Можно указать фактическое количество `quantity_fact` (не может быть меньше 0). "
            "Если сессия уже завершена (`status=completed`) — возвращается ошибка 400. "
            "Если актив не найден в сессии — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Marks an asset as checked within the specified inventory session. "
            "The asset is identified by `asset_id` or `material_id`. "
            "An optional actual quantity `quantity_fact` can be specified (must not be less than 0). "
            "If the session is already completed (`status=completed`), a 400 error is returned. "
            "If the asset is not found in the session, a 404 error is returned. "
            "User authorization is required."
    )
)
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
        material_id=data.material_id,
        checked_by=current_user.employee_id,
        quantity_fact=data.quantity_fact
    )
    if not success:
        raise HTTPException(status_code=404, detail="Актив не найден в этой сессии инвентаризации")
    return {"message": "success"}


@router_inventorization.post(
    "/sessions/{session_id}/check",
    summary="Отметить актив как проверенный / Mark Asset as Checked",
    description=(
            "RU: Отмечает актив как проверенный в рамках указанной сессии инвентаризации. "
            "Актив идентифицируется по `asset_id` или `material_id`. "
            "Можно указать фактическое количество `quantity_fact` (не может быть меньше 0). "
            "Если сессия уже завершена (`status=completed`) — возвращается ошибка 400. "
            "Если актив не найден в сессии — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Marks an asset as checked within the specified inventory session. "
            "The asset is identified by `asset_id` or `material_id`. "
            "An optional actual quantity `quantity_fact` can be specified (must not be less than 0). "
            "If the session is already completed (`status=completed`), a 400 error is returned. "
            "If the asset is not found in the session, a 404 error is returned. "
            "User authorization is required."
    )
)
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
        asset_id=data.asset_id,       # <-- ПЕРЕДАЕМ asset_id (может быть None)
        material_id=data.material_id, # <-- ПЕРЕДАЕМ material_id (может быть None)
        checked_by=current_user.employee_id,
        quantity_fact=data.quantity_fact
    )

    if not success:
        raise HTTPException(status_code=404, detail="Актив не найден в этой сессии инвентаризации")

    return {"message": "success"}


@router_inventorization.post(
    "/sessions/{session_id}/complete",
    response_model=InventorizationSessionResponse,
    summary="Завершить сессию инвентаризации / Complete Inventory Session",
    description=(
            "RU: Завершает сессию инвентаризации, устанавливая статус `completed`. "
            "После завершения изменение позиций (items) становится невозможным. "
            "Если сессия уже завершена — возвращается ошибка 400. "
            "Если сессия не найдена — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Completes an inventory session by setting the status to `completed`. "
            "After completion, modifying items is no longer possible. "
            "If the session is already completed, a 400 error is returned. "
            "If the session is not found, a 404 error is returned. "
            "User authorization is required."
    )
)
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
    summary="Получить отчёт по сессии инвентаризации / Get Inventory Session Report",
    description=(
            "RU: Возвращает сводный отчёт по указанной сессии инвентаризации: "
            "прогресс проверки, количество расхождений, излишков и недостач. "
            "Если сессия не найдена — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns a summary report for the specified inventory session: "
            "check progress, number of discrepancies, surpluses, and shortages. "
            "If the session is not found, a 404 error is returned. "
            "User authorization is required."
    )
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
    summary="Получить список расхождений инвентаризации / Get Inventory Discrepancies List",
    description=(
            "RU: Возвращает детальный список расхождений по указанной сессии инвентаризации: "
            "недостачи, излишки и непроверенные активы. "
            "Если сессия не найдена — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns a detailed list of discrepancies for the specified inventory session: "
            "shortages, surpluses, and unchecked assets. "
            "If the session is not found, a 404 error is returned. "
            "User authorization is required."
    )
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


@router_inventorization.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Удалить сессию инвентаризации / Delete Inventory Session",
    description=(
            "RU: Удаляет все позиции (items) указанной сессии инвентаризации, "
            "а затем удаляет саму сессию. Если сессия не найдена — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Deletes all items of the specified inventory session, "
            "and then deletes the session itself. If the session is not found, a 404 error is returned. "
            "User authorization is required."
    )
)
async def delete_status(
        session_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Удалить все элементы из сессии и удалить саму сессию инвентаризации"""
    db_status = await delete_inventorization_session(db, session_id)
    if not db_status:
        raise HTTPException(status_code=404, detail="Сессия инвентаризации не найдена")
    return {"message": "success"}


@router_inventorization.get(
    "/sessions/{session_id}/export/excel",
    summary="Экспорт сессии инвентаризации в Excel / Export Inventory Session to Excel",
    description=(
            "RU: Экспортирует данные указанной сессии инвентаризации в файл формата Excel (`.xlsx`) "
            "и возвращает его для скачивания. Если сессия не найдена или данные некорректны — "
            "возвращается ошибка 404. Авторизация не требуется (публичный эндпоинт для скачивания).\n\n"
            "EN: Exports the data of the specified inventory session to an Excel (`.xlsx`) file "
            "and returns it for download. If the session is not found or the data is invalid, "
            "a 404 error is returned. Authorization is not required (public endpoint for download)."
    )
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