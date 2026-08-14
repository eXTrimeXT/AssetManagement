from typing import Optional, Sequence
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.assets.Inventorization import InventorizationSession, InventorizationItem
from app.models.assets.Asset import Asset
from app.models.assets.AssetType import AssetType
from app.models.assets.AssetStatus import AssetStatus


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

# async def create_inventory_session(db: AsyncSession, asset_type_id: int) -> InventorizationSession:
#     # 1. Получаем информацию о типе актива
#     asset_type_result = await db.execute(
#         select(AssetType).where(AssetType.asset_type_id == asset_type_id)
#     )
#     asset_type = asset_type_result.scalar_one_or_none()
#
#     if not asset_type:
#         raise ValueError(f"Asset type with id {asset_type_id} not found")
#
#     # 2. Создаем сессию с денормализованными данными типа
#     session = InventorizationSession(
#         asset_type_id=asset_type_id,
#         asset_type_name=asset_type.name,
#         asset_type_en_name=asset_type.en_name,
#         status="in_progress"
#     )
#     db.add(session)
#     await db.flush()  # Получаем session.session_id
#
#     # 3. Копируем все активы нужного типа с денормализованными полями
#     result = await db.execute(
#         select(Asset).where(Asset.asset_type_id == asset_type_id)
#     )
#     assets = result.scalars().all()
#
#     items = [
#         InventorizationItem(
#             session_id=session.session_id,
#             asset_id=asset.asset_id,
#             asset_name=asset.name,
#             asset_inventory_id=asset.inventory_id,
#             asset_serial_number=asset.serial_number
#         )
#         for asset in assets
#     ]
#
#     db.add_all(items)
#     await db.commit()
#     await db.refresh(session)
#     return session
#
# async def check_inventory_item(db: AsyncSession, session_id: int, asset_id: int) -> bool:
#     result = await db.execute(
#         select(InventorizationItem).where(
#             InventorizationItem.session_id == session_id,
#             InventorizationItem.asset_id == asset_id
#         )
#     )
#     item = result.scalar_one_or_none()
#
#     if item:
#         item.is_checked = True
#         await db.commit()
#         return True
#     return False
#
# async def complete_inventory_session(db: AsyncSession, session_id: int) -> Optional[InventorizationSession]:
#     session = await get_inventory_session_by_id(db, session_id)
#     if not session:
#         return None
#
#     # 3. Находим все asset_id, которые НЕ были проверены (is_checked == False)
#     result = await db.execute(
#         select(InventorizationItem.asset_id).where(
#             InventorizationItem.session_id == session_id,
#             InventorizationItem.is_checked == False
#         )
#     )
#     unchecked_items = result.all()
#     unchecked_asset_ids = [item.asset_id for item in unchecked_items]
#
#     # # 4. Удаляем их из основной таблицы assets
#     # if unchecked_asset_ids:
#     #     await db.execute(delete(Asset).where(Asset.asset_id.in_(unchecked_asset_ids)))
#
#     # 4. Меняем статус на "Удален" для непроверенных активов
#     if unchecked_asset_ids:
#         await db.execute(
#             update(Asset)
#             .where(Asset.asset_id.in_(unchecked_asset_ids))
#             .values(asset_status="Удален")
#         )
#         # 5. Также обновляем статус в таблице inventorization_items
#         await db.execute(
#             update(InventorizationItem)
#             .where(
#                 InventorizationItem.session_id == session_id,
#                 InventorizationItem.asset_id.in_(unchecked_asset_ids)
#             )
#             .values(asset_status="deleted")
#         )
#
#     session.status = "completed"
#     await db.commit()
#     await db.refresh(session)
#     return session


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
            asset_inventory_id=asset.inventory_id,
            asset_serial_number=asset.serial_number,
            quantity=asset.quantity,        # копируем количество из актива
            quantity_fact=asset.quantity,   # копируем количество из актива
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


async def complete_inventory_session(db: AsyncSession, session_id: int) -> Optional[InventorizationSession]:
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
    unchecked_asset_ids = [item.asset_id for item in unchecked_items]

    # Меняем статус на "Удален" для непроверенных активов
    # (адаптировано под новую таблицу статусов: ищем id статуса "Удален")
    if unchecked_asset_ids:
        status_result = await db.execute(
            select(AssetStatus).where(AssetStatus.status == "Удален")
        )
        deleted_status = status_result.scalars().first()

        if deleted_status:
            await db.execute(
                update(Asset)
                .where(Asset.asset_id.in_(unchecked_asset_ids))
                .values(asset_status_id=deleted_status.id)
            )

        # Также обновляем статус в таблице inventorization_items
        await db.execute(
            update(InventorizationItem)
            .where(
                InventorizationItem.session_id == session_id,
                InventorizationItem.asset_id.in_(unchecked_asset_ids)
            )
            .values(asset_status="deleted")
        )

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
            .values(quantity=item.quantity_fact)
        )

    session.status = "completed"
    await db.commit()
    await db.refresh(session)
    return session