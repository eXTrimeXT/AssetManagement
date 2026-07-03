from typing import Optional, Sequence, List, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import date
from app.models.assets.asset_assignment import AssetAssignment
from app.schemas.assets.asset_assignment import AssetAssignmentCreate


async def create_assignment(
        db: AsyncSession,
        asset_id: int,
        data: AssetAssignmentCreate,
        assigned_by: str
) -> AssetAssignment | None:
    """
    Создать новое назначение.
    Автоматически закрывает все активные назначения этого сотрудника на этот актив.
    """
    # 1. Закрываем все активные назначения этого сотрудника на этот актив
    await close_active_assignments(db, asset_id, data.employee_id)

    # 2. Создаём новое назначение
    db_assignment = AssetAssignment(
        asset_id=asset_id,
        employee_id=data.employee_id,
        start_date=date.today(),
        end_date=None,  # Активная связь
        assigned_by=assigned_by,
        comment=data.comment
    )
    db.add(db_assignment)
    await db.commit()
    await db.refresh(db_assignment)

    # 3. Перезагружаем с связями
    return await get_assignment_by_id(db, db_assignment.id)


async def close_active_assignments(
        db: AsyncSession,
        asset_id: int,
        employee_id: str
) -> int:
    """
    Закрыть все активные назначения сотрудника на актив.
    Возвращает количество закрытых назначений.
    """
    result = await db.execute(
        select(AssetAssignment).where(
            and_(
                AssetAssignment.asset_id == asset_id,
                AssetAssignment.employee_id == employee_id,
                AssetAssignment.end_date.is_(None)
            )
        )
    )
    active_assignments = result.scalars().all()

    closed_count = 0
    for assignment in active_assignments:
        assignment.end_date = date.today()
        closed_count += 1

    if closed_count > 0:
        await db.commit()

    return closed_count


async def get_assignment_by_id(db: AsyncSession, assignment_id: int) -> Optional[AssetAssignment]:
    """Получить назначение по ID с загруженными связями"""
    result = await db.execute(
        select(AssetAssignment)
        .options(
            selectinload(AssetAssignment.employee),
            selectinload(AssetAssignment.assigner)
        )
        .where(AssetAssignment.id == assignment_id)
    )
    return result.scalar_one_or_none()


async def get_assignments_by_asset(
        db: AsyncSession,
        asset_id: int,
        active_only: bool = False
) -> Sequence[AssetAssignment]:
    """
    Получить все назначения актива.
    Если active_only=True — только активные (end_date IS NULL).
    """
    query = select(AssetAssignment).options(
        selectinload(AssetAssignment.employee),
        selectinload(AssetAssignment.assigner)
    ).where(AssetAssignment.asset_id == asset_id)

    if active_only:
        query = query.where(AssetAssignment.end_date.is_(None))

    query = query.order_by(AssetAssignment.start_date.desc())
    result = await db.execute(query)
    return result.scalars().all()


async def get_assignments_by_employee(
        db: AsyncSession,
        employee_id: str,
        active_only: bool = False
) -> Sequence[AssetAssignment]:
    """
    Получить все назначения сотрудника.
    Если active_only=True — только активные.
    """
    query = select(AssetAssignment).options(
        selectinload(AssetAssignment.employee),
        selectinload(AssetAssignment.assigner)
    ).where(AssetAssignment.employee_id == employee_id)

    if active_only:
        query = query.where(AssetAssignment.end_date.is_(None))

    query = query.order_by(AssetAssignment.start_date.desc())
    result = await db.execute(query)
    return result.scalars().all()


async def get_active_assignments_for_asset(
        db: AsyncSession,
        asset_id: int
) -> Sequence[Any]:
    """Получить все активные назначения актива (текущие пользователи)"""
    result = await db.execute(
        select(AssetAssignment)
        .options(selectinload(AssetAssignment.employee))
        .where(
            and_(
                AssetAssignment.asset_id == asset_id,
                AssetAssignment.end_date.is_(None)
            )
        )
    )
    return result.scalars().all()


async def delete_assignment(db: AsyncSession, assignment_id: int) -> bool:
    """Удалить назначение (только неактивные)"""
    assignment = await get_assignment_by_id(db, assignment_id)
    if not assignment:
        return False

    # Нельзя удалить активное назначение — нужно закрыть его
    if assignment.end_date is None:
        return False

    await db.delete(assignment)
    await db.commit()
    return True


async def close_assignment(db: AsyncSession, assignment_id: int) -> Optional[AssetAssignment]:
    """Закрыть активное назначение (установить end_date)"""
    assignment = await get_assignment_by_id(db, assignment_id)
    if not assignment:
        return None

    if assignment.end_date is not None:
        return assignment  # Уже закрыто

    assignment.end_date = date.today()
    await db.commit()
    await db.refresh(assignment)
    return assignment