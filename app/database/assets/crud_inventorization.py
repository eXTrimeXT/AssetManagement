from typing import Optional, Sequence
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.assets.Inventorization import InventorizationSession, InventorizationItem
from app.models.assets.Asset import Asset

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

async def create_inventory_session(db: AsyncSession, asset_type_id: int) -> InventorizationSession:
    # 1. Создаем сессию
    session = InventorizationSession(asset_type_id=asset_type_id, status="in_progress")
    db.add(session)
    await db.flush()  # Получаем session.id

    # 2. Копируем все asset_id нужного типа в промежуточную таблицу
    result = await db.execute(
        select(Asset.asset_id).where(Asset.asset_type_id == asset_type_id)
    )
    assets = result.all()
    items = [InventorizationItem(session_id=session.session_id, asset_id=asset.asset_id) for asset in assets]

    db.add_all(items)
    await db.commit()
    await db.refresh(session)
    return session

async def check_inventory_item(db: AsyncSession, session_id: int, asset_id: int) -> bool:
    result = await db.execute(
        select(InventorizationItem).where(
            InventorizationItem.session_id == session_id,
            InventorizationItem.asset_id == asset_id
        )
    )
    item = result.scalar_one_or_none()

    if item:
        item.is_checked = True
        await db.commit()
        return True
    return False

async def complete_inventory_session(db: AsyncSession, session_id: int) -> Optional[InventorizationSession]:
    session = await get_inventory_session_by_id(db, session_id)
    if not session:
        return None

    # 3. Находим все asset_id, которые НЕ были проверены (is_checked == False)
    result = await db.execute(
        select(InventorizationItem.asset_id).where(
            InventorizationItem.session_id == session_id,
            InventorizationItem.is_checked == False
        )
    )
    unchecked_items = result.all()
    unchecked_asset_ids = [item.asset_id for item in unchecked_items]

    # 4. Удаляем их из основной таблицы assets
    if unchecked_asset_ids:
        await db.execute(delete(Asset).where(Asset.asset_id.in_(unchecked_asset_ids)))

    session.status = "completed"
    await db.commit()
    await db.refresh(session)
    return session