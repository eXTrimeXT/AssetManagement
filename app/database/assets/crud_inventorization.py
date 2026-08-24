from typing import Optional, Sequence
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.assets.Inventorization import InventorizationSession, InventorizationItem
from app.models.assets.Asset import Asset
from app.models.assets.AssetType import AssetType


async def get_inventory_session_by_id(db: AsyncSession, session_id: int) -> Optional[InventorizationSession]:
    result = await db.execute(
        select(InventorizationSession)
        .options(selectinload(InventorizationSession.items))
        .where(InventorizationSession.session_id == session_id)
    )
    return result.scalar_one_or_none()

async def get_inventory_sessions_list(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[InventorizationSession]:
    query = select(InventorizationSession).options(selectinload(InventorizationSession.items)).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def get_inventory_items_by_session_id(db: AsyncSession, session_id: int) -> Sequence[InventorizationItem]:
    result = await db.execute(
        select(InventorizationItem)
        .where(InventorizationItem.session_id == session_id)
    )
    return result.scalars().all()

async def create_inventory_session(db: AsyncSession, asset_type_id: int) -> InventorizationSession:
    # Получаем информацию о типе актива
    asset_type_result = await db.execute(
        select(AssetType).where(AssetType.asset_type_id == asset_type_id)
    )
    asset_type = asset_type_result.scalar_one_or_none()

    if not asset_type:
        raise ValueError(f"Asset type with id {asset_type_id} not found")

    # Создаем сессию с денормализованными данными типа
    session = InventorizationSession(
        asset_type_id=asset_type_id,
        asset_type_name=asset_type.name,
        asset_type_en_name=asset_type.en_name,
        status="in_progress"
    )
    db.add(session)
    await db.flush()

    # Копируем все активы нужного типа с денормализованными полями
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
            serial_number=asset.serial_number, # Копируем серийный номер для будущего поиска по сканированию для Android
            quantity=asset.quantity,        # копируем количество из актива
            quantity_fact=None,             # ставим None - значит кол-во факт не известно
        )
        for asset in assets
    ]

    db.add_all(items)
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


async def complete_inventory_session(db: AsyncSession, session_id: int, updated_by: str) -> Optional[InventorizationSession]:
    session = await get_inventory_session_by_id(db, session_id)
    if not session:
        return None

    # === ПРОВЕРКА: нельзя завершить уже завершенную сессию ===
    if session.status == "completed":
        raise ValueError("Сессия уже завершена.")
    # =========================================================

    # Находим все asset_id, которые НЕ были проверены (is_checked == False)
    result = await db.execute(
        select(InventorizationItem.asset_id).where(
            InventorizationItem.session_id == session_id,
            InventorizationItem.is_checked == False
        )
    )
    unchecked_items = result.all()

    # === при завершении меняем quantity на quantity_fact ===
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

    session.status = "completed"
    await db.commit()
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