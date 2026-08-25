import logging
from typing import Optional, Sequence, Tuple
from datetime import datetime, date
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assets.Asset import Asset
from app.models.assets.AssetWriteOff import AssetWriteOff, WriteOffStatus
from app.models.assets.AssetStatus import AssetStatus
from app.models.assets.AssetAssignment import AssetAssignment
from app.schemas.assets.AssetWriteOffSchemas import WriteOffRequest, WriteOffRejectRequest
from app.database.assets.crud_asset_history import create_history_record


from app.database.crud_notifications import notify_write_off_requested, notify_write_off_rejected, \
    notify_write_off_approved, notify_unassigned_responsible, notify_unassigned_user

logger = logging.getLogger(__name__)

WRITTEN_OFF_STATUS = "Списан"


async def get_or_create_written_off_status(db: AsyncSession) -> AssetStatus:
    """Получить или создать статус 'Списан'."""
    result = await db.execute(
        select(AssetStatus).where(AssetStatus.status == WRITTEN_OFF_STATUS)
    )
    status = result.scalars().first()
    if status:
        return status

    new_status = AssetStatus(status=WRITTEN_OFF_STATUS)
    db.add(new_status)
    await db.flush()
    return new_status


async def create_write_off_request(
        db: AsyncSession,
        asset_id: int,
        data: WriteOffRequest,
        requested_by: str,
) -> AssetWriteOff:
    """
    Создать заявку на списание.

    Уведомление приходит ответственным за актив.
    """
    # Проверяем существование актива
    asset = await db.execute(select(Asset).where(Asset.asset_id == asset_id))
    asset_obj = asset.scalar_one_or_none()
    if not asset_obj:
        raise ValueError("Актив не найден")

    # Проверяем, нет ли уже активной заявки
    existing = await db.execute(
        select(AssetWriteOff).where(
            AssetWriteOff.asset_id == asset_id,
            AssetWriteOff.status == WriteOffStatus.PENDING,
            )
    )
    if existing.scalar_one_or_none():
        raise ValueError("По этому активу уже есть заявка на списание")

    # Создаём заявку
    write_off = AssetWriteOff(
        asset_id=asset_id,
        reason=data.reason,
        write_off_type=data.write_off_type.value,
        requested_by=requested_by,
        status=WriteOffStatus.PENDING,
    )
    db.add(write_off)
    await db.flush()

    # === Уведомляем ответственных за актив ===
    assignments_result = await db.execute(
        select(AssetAssignment).where(
            AssetAssignment.asset_id == asset_id,
            AssetAssignment.assignment_type == "responsible",
            AssetAssignment.end_date.is_(None),
            )
    )
    responsibles = assignments_result.scalars().all()

    notified_count = 0
    for assignment in responsibles:
        # Не уведомляем самого инициатора
        # if assignment.employee_id != requested_by:
        await notify_write_off_requested(
            db=db,
            employee_id=assignment.employee_id,
            asset_id=asset_id,
            initiator_id=requested_by,
        )
        notified_count += 1

    logger.info(
        f"[WriteOff] Создана заявка #{write_off.write_off_id} на актив {asset_id}. "
        f"Уведомлено ответственных: {notified_count}."
    )

    # Записываем в историю
    await create_history_record(
        db=db,
        asset_id=asset_id,
        field_name="write_off_requested",
        old_value=None,
        new_value=data.reason[:100],
        changed_by=requested_by,
    )

    await db.commit()
    await db.refresh(write_off)
    return write_off


async def get_write_off_by_id(
        db: AsyncSession,
        write_off_id: int,
) -> Optional[AssetWriteOff]:
    result = await db.execute(
        select(AssetWriteOff)
        .where(AssetWriteOff.write_off_id == write_off_id)
    )
    return result.scalar_one_or_none()


async def get_write_offs_list(
        db: AsyncSession,
        status: Optional[str] = None,
        asset_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
) -> Tuple[Sequence[AssetWriteOff], int]:
    """Получить список заявок с фильтрами."""
    filters = []
    if status:
        filters.append(AssetWriteOff.status == status)
    if asset_id:
        filters.append(AssetWriteOff.asset_id == asset_id)

    # Подсчёт
    count_query = select(func.count(AssetWriteOff.write_off_id))
    if filters:
        count_query = count_query.where(and_(*filters))
    total = (await db.execute(count_query)).scalar_one()

    # Данные
    query = (
        select(AssetWriteOff)
        .options(
            selectinload(AssetWriteOff.asset),
            selectinload(AssetWriteOff.requester),
            selectinload(AssetWriteOff.approver),
        )
    )
    if filters:
        query = query.where(and_(*filters))
    query = query.order_by(AssetWriteOff.requested_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    return result.scalars().all(), total


async def approve_write_off(
        db: AsyncSession,
        write_off_id: int,
        approved_by: str,
) -> AssetWriteOff:
    """
    Утвердить заявку на списание.
    1. Меняем статус заявки
    2. Меняем статус актива на 'Списан'
    3. Закрываем все активные привязки
    4. Уведомляем инициатора
    """
    write_off = await get_write_off_by_id(db, write_off_id)
    if not write_off:
        raise ValueError("Заявка не найдена")
    if write_off.status != WriteOffStatus.PENDING:
        raise ValueError("Заявка уже обработана")

    # Утверждаем
    write_off.status = WriteOffStatus.APPROVED
    write_off.approved_by = approved_by
    write_off.approved_at = datetime.now()

    # Меняем статус актива
    written_off_status = await get_or_create_written_off_status(db)
    asset_result = await db.execute(
        select(Asset).where(Asset.asset_id == write_off.asset_id)
    )
    asset = asset_result.scalar_one_or_none()
    if asset:
        old_status_id = asset.asset_status_id
        asset.asset_status_id = written_off_status.id
        asset.updated_by = approved_by

        # Записываем изменение статуса в историю
        await create_history_record(
            db=db,
            asset_id=asset.asset_id,
            field_name="asset_status_id",
            old_value=str(old_status_id),
            new_value=str(written_off_status.id),
            changed_by=approved_by,
        )

    # Закрываем все активные привязки + уведомляем бывших владельцев
    assignments_result = await db.execute(
        select(AssetAssignment).where(
            AssetAssignment.asset_id == write_off.asset_id,
            AssetAssignment.end_date.is_(None),
            )
    )
    assignments = assignments_result.scalars().all()
    for assignment in assignments:
        assignment.end_date = date.today()

        # Уведомление об отвязке
        if assignment.assignment_type == "user":
            await notify_unassigned_user(
                db=db,
                employee_id=assignment.employee_id,
                asset_id=assignment.asset_id,
                initiator_id=approved_by,
            )
        else:
            await notify_unassigned_responsible(
                db=db,
                employee_id=assignment.employee_id,
                asset_id=assignment.asset_id,
                initiator_id=approved_by,
            )

    # Уведомляем инициатора об утверждении
    # if write_off.requested_by != approved_by:
    await notify_write_off_approved(
        db=db,
        employee_id=write_off.requested_by,
        asset_id=write_off.asset_id,
        initiator_id=approved_by,
    )

    await db.commit()
    await db.refresh(write_off)
    return write_off


async def reject_write_off(
        db: AsyncSession,
        write_off_id: int,
        approved_by: str,
        data: WriteOffRejectRequest,
) -> AssetWriteOff:
    """Отклонить заявку на списание."""
    write_off = await get_write_off_by_id(db, write_off_id)
    if not write_off:
        raise ValueError("Заявка не найдена")
    if write_off.status != WriteOffStatus.PENDING:
        raise ValueError("Заявка уже обработана")

    write_off.status = WriteOffStatus.REJECTED
    write_off.approved_by = approved_by
    write_off.approved_at = datetime.now()
    write_off.reject_reason = data.reject_reason

    # Уведомляем инициатора
    # if write_off.requested_by != approved_by:
    await notify_write_off_rejected(
        db=db,
        employee_id=write_off.requested_by,
        asset_id=write_off.asset_id,
        initiator_id=approved_by,
    )

    await db.commit()
    await db.refresh(write_off)
    return write_off