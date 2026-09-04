from datetime import datetime
from typing import Optional, Sequence, Tuple

import logging
from sqlalchemy import select, update, distinct, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.inventorization.Inventorization import InventorizationSession, InventorizationItem
from app.models.assets.Asset import Asset
from app.models.assets.AssetType import AssetType
from app.models.assets.AssetAssignment import AssetAssignment
from app.database.crud_notifications import notify_inventory_started, notify_inventory_completed

logger = logging.getLogger(__name__)


async def get_inventory_session_by_id(db: AsyncSession, session_id: int) -> Optional[InventorizationSession]:
    result = await db.execute(
        select(InventorizationSession)
        .options(selectinload(InventorizationSession.items))
        .where(InventorizationSession.session_id == session_id)
    )
    return result.scalar_one_or_none()


async def get_inventory_sessions_list(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[
    InventorizationSession]:
    query = select(InventorizationSession).options(selectinload(InventorizationSession.items)).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_inventory_items_by_session_id(
        db: AsyncSession,
        session_id: int,
        page: int = 1,
        page_size: int = 50
) -> Tuple[Sequence[InventorizationItem], int]:
    """Получить элементы сессии инвентаризации с пагинацией. Возвращает (items, total_count)"""

    # 1. Получаем общее количество записей для этой сессии
    count_query = select(func.count(InventorizationItem.inventorization_id)).where(
        InventorizationItem.session_id == session_id
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 2. Получаем пагинированный список элементов
    offset = (page - 1) * page_size
    items_query = (
        select(InventorizationItem)
        .where(InventorizationItem.session_id == session_id)
        .order_by(InventorizationItem.inventorization_id) # Добавляем порядок для стабильной пагинации
        .offset(offset)
        .limit(page_size)
    )
    items_result = await db.execute(items_query)
    items = items_result.scalars().all()

    return items, total


async def create_inventory_session(
        db: AsyncSession,
        asset_type_id: int,
        creator_employee_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
) -> InventorizationSession:
    asset_type_result = await db.execute(
        select(AssetType).where(AssetType.asset_type_id == asset_type_id)
    )
    asset_type = asset_type_result.scalar_one_or_none()

    if not asset_type:
        raise ValueError(f"Asset type with id {asset_type_id} not found")

    session = InventorizationSession(
        asset_type_id=asset_type_id,
        asset_type_name=asset_type.name,
        asset_type_en_name=asset_type.en_name,
        status="in_progress",
        created_by=creator_employee_id,
        start_date=start_date,
        end_date=end_date
    )
    db.add(session)
    await db.flush()

    result = await db.execute(
        select(Asset).where(Asset.asset_type_id == asset_type_id)
    )
    assets = result.scalars().all()

    items = [
        InventorizationItem(
            session_id=session.session_id,
            asset_id=asset.asset_id,
            asset_name=asset.name,
            is_checked=False,
            serial_number=asset.serial_number,
            quantity=asset.quantity,
            quantity_fact=None,
        )
        for asset in assets
    ]
    db.add_all(items)
    await db.flush()  # Важно сделать flush, чтобы получить session_id и asset_ids

    # === НОВАЯ ЛОГИКА УВЕДОМЛЕНИЙ ===
    # Находим всех уникальных сотрудников, которые имеют активы из этой сессии
    asset_ids = [item.asset_id for item in items]

    if asset_ids:
        # Ищем активных ответственных или пользователей этих активов
        employees_result = await db.execute(
            select(distinct(AssetAssignment.employee_id)).where(
                AssetAssignment.asset_id.in_(asset_ids),
                AssetAssignment.end_date.is_(None)  # Только активные назначения
            )
        )
    responsible_employees = [row[0] for row in employees_result.all()]

    # Отправляем ОДНО уведомление каждому уникальному сотруднику
    for emp_id in responsible_employees:
        await notify_inventory_started(
            db=db,
            employee_id=emp_id,
            session_id=session.session_id,
            initiator_id=creator_employee_id,
        )

    await db.commit()
    await db.refresh(session)
    return session


async def check_inventory_item(
        db: AsyncSession,
        session_id: int,
        asset_id: int,
        quantity_fact: Optional[int] = None
) -> bool:
    # === ПРОВЕРКА: quantity_fact не может быть меньше 0 ===
    if quantity_fact is not None and quantity_fact < 0:
        raise ValueError("quantity_fact не может быть меньше 0")

    # === ПРОВЕРКА: сессия не должна быть completed ===
    session = await get_inventory_session_by_id(db, session_id)
    if not session:
        return False
    if session.status == "completed":
        raise ValueError("Сессия уже завершена. Изменять items нельзя.")
    # ===================================================

    result = await db.execute(
        select(InventorizationItem).where(
            InventorizationItem.session_id == session_id,
            InventorizationItem.asset_id == asset_id
        )
    )
    item = result.scalar_one_or_none()

    if item:
        item.is_checked = True
        item.quantity_fact = quantity_fact
        await db.commit()
        return True
    return False


async def complete_inventory_session(db: AsyncSession, session_id: int, updated_by: str) -> Optional[
    InventorizationSession]:
    session = await get_inventory_session_by_id(db, session_id)
    if not session:
        raise ValueError("Сессия не найдена.")
    if session.status == "completed":
        raise ValueError("Сессия уже завершена.")

    # Обновляем количества в активах
    result = await db.execute(
        select(InventorizationItem).where(
            InventorizationItem.session_id == session_id,
            InventorizationItem.is_checked == True,
            InventorizationItem.quantity_fact.isnot(None)
        )
    )
    checked_items = result.scalars().all()

    for item in checked_items:
        await db.execute(
            update(Asset)
            .where(Asset.asset_id == item.asset_id)
            .values(quantity=item.quantity_fact, updated_by=updated_by)
        )

    # Меняем статус сессии
    session.status = "completed"
    session.end_date = datetime.now()

    # Находим всех ответственных для уведомлений
    result_assets = await db.execute(
        select(InventorizationItem.asset_id).where(InventorizationItem.session_id == session_id)
    )
    asset_ids = [row[0] for row in result_assets.all()]

    responsible_employees = []
    if asset_ids:
        employees_result = await db.execute(
            select(distinct(AssetAssignment.employee_id)).where(
                AssetAssignment.asset_id.in_(asset_ids),
                AssetAssignment.end_date.is_(None)  # Только активные назначения
            )
        )
        responsible_employees = [row[0] for row in employees_result.all()]

    # Создаем уведомления (они пока только в состоянии flush)
    for emp_id in responsible_employees:
        await notify_inventory_completed(
            db=db,
            employee_id=emp_id,
            session_id=session_id,
            initiator_id=updated_by,
        )

    if not responsible_employees:
        logger.debug(f"Ответственные не найдены для сессии {session.session_id}. Уведомляем создателя.")
        await notify_inventory_started(
            db=db,
            employee_id=updated_by,
            session_id=session.session_id,
            initiator_id=updated_by,
        )

    # Сохраняем и сессию, и созданные уведомления в БД!
    await db.commit()

    # Обновляем объект сессии для возврата
    await db.refresh(session)
    return session


""" Списание """


async def get_inventorization_report(
        db: AsyncSession,
        session_id: int,
) -> Optional[dict]:
    """Получить сводный отчёт по сессии инвентаризации."""
    session = await get_inventory_session_by_id(db, session_id)
    if not session:
        return None

    result = await db.execute(
        select(InventorizationItem).where(
            InventorizationItem.session_id == session_id
        )
    )
    items = result.scalars().all()

    total = len(items)
    checked = sum(1 for i in items if i.is_checked)
    unchecked = total - checked

    matches = 0
    discrepancies = 0
    surplus = 0
    missing = 0

    for item in items:
        if not item.is_checked:
            continue
        if item.quantity_fact is None:
            continue

        if item.quantity == item.quantity_fact:
            matches += 1
        else:
            discrepancies += 1
            if item.quantity_fact > (item.quantity or 0):
                surplus += 1
            else:
                missing += 1

    progress = (checked / total * 100) if total > 0 else 0.0

    return {
        "session_id": session.session_id,
        "asset_type_id": session.asset_type_id,
        "asset_type_name": session.asset_type_name,
        "status": session.status,
        "created_at": session.created_at,
        "start_date": session.start_date,
        "end_date": session.end_date,
        "total_items": total,
        "checked_items": checked,
        "unchecked_items": unchecked,
        "progress_percent": round(progress, 2),
        "matches_count": matches,
        "discrepancies_count": discrepancies,
        "surplus_count": surplus,
        "missing_count": missing,
        "not_checked_count": unchecked,
    }


async def get_inventorization_discrepancies(
        db: AsyncSession,
        session_id: int,
) -> Optional[dict]:
    """Получить список расхождений по сессии."""
    session = await get_inventory_session_by_id(db, session_id)
    if not session:
        return None

    result = await db.execute(
        select(InventorizationItem).where(
            InventorizationItem.session_id == session_id
        )
    )
    items = result.scalars().all()

    discrepancies = []
    for item in items:
        # Пропускаем полностью совпадающие
        if item.is_checked and item.quantity == item.quantity_fact:
            continue

        # Определяем тип расхождения
        if not item.is_checked:
            discrepancy_type = "not_checked"
            difference = None
        elif item.quantity_fact is None:
            discrepancy_type = "not_checked"
            difference = None
        elif item.quantity_fact > (item.quantity or 0):
            discrepancy_type = "surplus"
            difference = item.quantity_fact - (item.quantity or 0)
        elif item.quantity_fact < (item.quantity or 0):
            discrepancy_type = "missing"
            difference = item.quantity_fact - (item.quantity or 0)
        else:
            continue

        # Получаем serial_number из актива
        asset_result = await db.execute(
            select(Asset.serial_number).where(Asset.asset_id == item.asset_id)
        )
        serial_number = asset_result.scalar_one_or_none()

        discrepancies.append({
            "inventorization_id": item.inventorization_id,
            "asset_id": item.asset_id,
            "asset_name": item.asset_name,
            "serial_number": serial_number,
            "quantity": item.quantity,
            "quantity_fact": item.quantity_fact,
            "difference": difference,
            "discrepancy_type": discrepancy_type,
        })

    return {
        "session_id": session_id,
        "total_discrepancies": len(discrepancies),
        "items": discrepancies,
    }

async def delete_inventorization_session(db: AsyncSession, session_id: int) -> bool:
    obj = await get_inventory_session_by_id(db, session_id)
    if not obj:
        return False

    await db.delete(obj)
    await db.commit()
    return True