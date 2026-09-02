from typing import Optional, Sequence
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from app.models.assets.AssetAssignment import AssetAssignment, AssignmentTypeEnum
from app.schemas.assets.AssetAssignmentSchemas import AssetAssignmentCreate
from app.database.crud_notifications import (
    notify_assigned_user,
    notify_assigned_responsible,
    notify_assigned_serving,
    notify_unassigned_user,
    notify_unassigned_responsible,
    notify_unassigned_serving,
    notify_assignment_declined,
)


async def create_assignment(
        db: AsyncSession,
        data: AssetAssignmentCreate,
        assigned_by: str
) -> AssetAssignment:
    """
    Создать новое назначение.
    НЕ закрывает привязки других типов — сотрудник может быть одновременно user и responsible.
    Создаёт уведомление сотруднику о назначении.
    """
    # 1. Проверяем, существует ли уже активная привязка того же типа
    result = await db.execute(
        select(AssetAssignment).where(
            and_(
                AssetAssignment.asset_id == data.asset_id,
                AssetAssignment.employee_id == data.employee_id,
                AssetAssignment.assignment_type == data.assignment_type,
                AssetAssignment.end_date.is_(None),
                )
        )
    )
    existing = result.scalars().first()
    if existing:
        # Уже существует активная привязка того же типа — возвращаем её без изменений
        return existing

    # Сброс флага is_current у старых записей
    if data.is_current:
        reset_query = (
            select(AssetAssignment)
            .where(
                and_(
                    AssetAssignment.asset_id == data.asset_id,
                    AssetAssignment.assignment_type == data.assignment_type,
                    AssetAssignment.end_date.is_(None), # Только активные
                    AssetAssignment.is_current == True
                )
            )
        )
        result = await db.execute(reset_query)
        old_primary_assignments = result.scalars().all()
        for old_assignment in old_primary_assignments:
            old_assignment.is_current = False

    # Создаём новое назначение
    db_assignment = AssetAssignment(
        asset_id=data.asset_id,
        employee_id=data.employee_id,
        start_date=date.today(),
        end_date=None,
        assigned_by=assigned_by,
        assignment_type=data.assignment_type,
        comment=data.comment
    )
    db.add(db_assignment)
    await db.flush()

    # Создаём уведомление сотруднику о назначении
    if data.assignment_type == AssignmentTypeEnum.USER:
        await notify_assigned_user(
            db=db,
            employee_id=data.employee_id,
            asset_id=data.asset_id,
            initiator_id=assigned_by,
        )
    elif data.assignment_type == AssignmentTypeEnum.RESPONSIBLE:
        await notify_assigned_responsible(
            db=db,
            employee_id=data.employee_id,
            asset_id=data.asset_id,
            initiator_id=assigned_by,
        )
    elif data.assignment_type == AssignmentTypeEnum.SERVING:
        await notify_assigned_serving(
            db=db,
            employee_id=data.employee_id,
            asset_id=data.asset_id,
            initiator_id=assigned_by,
        )

    await db.commit()
    await db.refresh(db_assignment)
    return db_assignment


async def close_active_assignments(
        db: AsyncSession,
        asset_id: int,
        employee_id: str,
        closed_by: Optional[str] = None,
        exclude_type: Optional[str] = None,
) -> int:
    """
    Закрыть все активные назначения сотрудника на актив.
    Создаёт уведомления об отвязке для каждого закрытого назначения.

    Args:
        exclude_type: если указан, назначения этого типа не закрываются
                      (чтобы не закрыть только что созданную привязку того же типа)
    """
    query = select(AssetAssignment).where(
        and_(
            AssetAssignment.asset_id == asset_id,
            AssetAssignment.employee_id == employee_id,
            AssetAssignment.end_date.is_(None)
        )
    )
    if exclude_type:
        query = query.where(AssetAssignment.assignment_type != exclude_type)

    result = await db.execute(query)
    active_assignments = result.scalars().all()

    closed_count = 0
    for assignment in active_assignments:
        assignment.end_date = date.today()
        closed_count += 1

        # Уведомление об отвязке
        if assignment.assignment_type == AssignmentTypeEnum.USER:
            await notify_unassigned_user(
                db=db,
                employee_id=assignment.employee_id,
                asset_id=assignment.asset_id,
                initiator_id=closed_by or assignment.assigned_by,
            )
        elif assignment.assignment_type == AssignmentTypeEnum.RESPONSIBLE:
            await notify_unassigned_responsible(
                db=db,
                employee_id=assignment.employee_id,
                asset_id=assignment.asset_id,
                initiator_id=closed_by or assignment.assigned_by,
            )
        elif assignment.assignment_type == AssignmentTypeEnum.SERVING:
            await notify_unassigned_serving(
                db=db,
                employee_id=assignment.employee_id,
                asset_id=assignment.asset_id,
                initiator_id=closed_by or assignment.assigned_by,
            )
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


async def get_all_assignments(
        db: AsyncSession,
        active_only: bool = False
) -> Sequence[AssetAssignment]:
    """Получить все назначения"""
    query = select(AssetAssignment)
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


async def close_assignment(
        db: AsyncSession,
        assignment_id: int,
        closed_by: Optional[str] = None,
) -> Optional[AssetAssignment]:
    """
    Закрыть активное назначение.
    Создаёт уведомление сотруднику об отвязке.

    Args:
        closed_by: кто закрыл привязку (employee_id). Если не указан, используется assigned_by.
        :param db:
        :param assignment_id:
        :param closed_by:
    """
    assignment = await get_assignment_by_id(db, assignment_id)
    if not assignment:
        return None
    if assignment.end_date is not None:
        return assignment

    assignment.end_date = date.today()

    # Уведомление об отвязке
    initiator = closed_by or assignment.assigned_by
    if assignment.assignment_type == "user":
        await notify_unassigned_user(
            db=db,
            employee_id=assignment.employee_id,
            asset_id=assignment.asset_id,
            initiator_id=initiator,
        )
    elif assignment.assignment_type == "responsible":
        await notify_unassigned_responsible(
            db=db,
            employee_id=assignment.employee_id,
            asset_id=assignment.asset_id,
            initiator_id=initiator,
        )

    await db.commit()
    await db.refresh(assignment)
    return assignment

async def decline_assignment(
        db: AsyncSession,
        asset_id: int,
        employee_id: str,
) -> Optional[AssetAssignment]:
    """
    Отказаться от актива: закрывает активную привязку (end_date = сегодня)
    и создает уведомление для того, кто её создал (assigned_by).
    """
    # Ищем активную привязку текущего пользователя к этому активу
    result = await db.execute(
        select(AssetAssignment).where(
            and_(
                AssetAssignment.asset_id == asset_id,
                AssetAssignment.employee_id == employee_id,
                AssetAssignment.end_date.is_(None)
            )
        )
    )
    assignment = result.scalar_one_or_none()

    if not assignment:
        return None # Активной привязки не найдено

    # Закрываем привязку
    assignment.end_date = date.today()

    # Создаем уведомление для инициатора привязки (assigned_by)
    await notify_assignment_declined(
        db=db,
        employee_id=assignment.assigned_by, # Тот, кто назначал
        asset_id=asset_id,
        initiator_id=employee_id,          # Тот, кто отказался (current_user)
        assignment_type=assignment.assignment_type
    )

    await db.commit()
    await db.refresh(assignment)
    return assignment