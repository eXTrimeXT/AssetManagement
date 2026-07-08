from typing import Optional, Sequence
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from app.models.assets.asset_assignment import AssetAssignment
from app.schemas.assets.asset_assignment import AssetAssignmentCreate


async def create_assignment(
        db: AsyncSession,
        data: AssetAssignmentCreate,
        assigned_by: str
) -> AssetAssignment:
    """
    Создать новое назначение.
    Автоматически закрывает все активные назначения этого сотрудника на этот актив.
    """
    # 1. Закрываем все активные назначения этого сотрудника на этот актив
    await close_active_assignments(db, data.asset_id, data.employee_id)

    # 2. Создаём новое назначение
    db_assignment = AssetAssignment(
        asset_id=data.asset_id,
        employee_id=data.employee_id,
        start_date=date.today(),
        end_date=None,
        assigned_by=assigned_by,
        comment=data.comment
    )
    db.add(db_assignment)
    await db.commit()
    await db.refresh(db_assignment)
    return db_assignment


async def close_active_assignments(
        db: AsyncSession,
        asset_id: int,
        employee_id: str
) -> int:
    """Закрыть все активные назначения сотрудника на актив."""
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
    result = await db.execute(
        select(AssetAssignment).where(AssetAssignment.id == assignment_id)
    )
    return result.scalar_one_or_none()


async def get_assignments_by_asset(
        db: AsyncSession,
        asset_id: int,
        active_only: bool = False
) -> Sequence[AssetAssignment]:
    """Получить все назначения актива."""
    query = select(AssetAssignment).where(AssetAssignment.asset_id == asset_id)
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
    """Получить все назначения сотрудника."""
    query = select(AssetAssignment).where(AssetAssignment.employee_id == employee_id)
    if active_only:
        query = query.where(AssetAssignment.end_date.is_(None))
    query = query.order_by(AssetAssignment.start_date.desc())
    result = await db.execute(query)
    return result.scalars().all()


async def delete_assignment(db: AsyncSession, assignment_id: int) -> bool:
    """Удалить назначение (только неактивные)."""
    assignment = await get_assignment_by_id(db, assignment_id)
    if not assignment:
        return False
    if assignment.end_date is None:
        return False
    await db.delete(assignment)
    await db.commit()
    return True


async def close_assignment(db: AsyncSession, assignment_id: int) -> Optional[AssetAssignment]:
    """Закрыть активное назначение."""
    assignment = await get_assignment_by_id(db, assignment_id)
    if not assignment:
        return None
    if assignment.end_date is not None:
        return assignment
    assignment.end_date = date.today()
    await db.commit()
    await db.refresh(assignment)
    return assignment