import logging
from typing import Optional
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from sqlalchemy.sql.functions import func

from app.models.assets.Asset import Asset
from app.models.assets.AssetAssignment import AssetAssignment
from app.models.assets.AssetConfirmation import AssetConfirmation, AssetConfirmationStatus
from app.models.notifications.Notification import Notification, NotificationStatus, NotificationEventType
from app.schemas.assets.AssetConfirmationSchemas import CreateConfirmationRequest, ConfirmAssetRequest
from app.models.zup import Employee
from app.database.zup.crud_zup_employees import get_employee_full_name

logger = logging.getLogger(__name__)


async def _get_asset_by_identifiers(
        db: AsyncSession,
        asset_id: Optional[int] = None,
) -> Optional[Asset]:
    """Поиск актива в локальной БД по ID"""
    if asset_id:
        result = await db.execute(select(Asset).where(Asset.asset_id == asset_id))
        return result.scalar_one_or_none()
    return None


async def create_confirmation_request(
        db: AsyncSession,
        request: CreateConfirmationRequest,
        requested_by: str
) -> dict:
    """
    Создает заявку на подтверждение и отправляет уведомления.
    Работает только с локальной базой данных.
    """
    created_count = 0
    target_asset = None

    # 1. Ищем актив, если он указан
    if request.asset_id:
        target_asset = await _get_asset_by_identifiers(db, asset_id=request.asset_id)
        if not target_asset:
            raise ValueError("Актив не найден в локальной базе данных по указанным данным")

    # ==============================================================================
    # СЦЕНАРИЙ 1: Указаны И сотрудник, И конкретный актив
    # ==============================================================================
    if request.employee_id and target_asset:
        assignment_stmt = select(AssetAssignment).where(
            AssetAssignment.asset_id == target_asset.asset_id,
            AssetAssignment.employee_id == request.employee_id,
            AssetAssignment.end_date.is_(None)
        )
        assignments = (await db.execute(assignment_stmt)).scalars().all()

        if not assignments:
            raise ValueError(f"Сотрудник {request.employee_id} не числится ответственным за актив {target_asset.asset_id}")

        existing = await db.execute(select(AssetConfirmation).where(
            AssetConfirmation.asset_id == target_asset.asset_id,
            AssetConfirmation.employee_id == request.employee_id,
            AssetConfirmation.status == AssetConfirmationStatus.PENDING
        ))
        if existing.scalar_one_or_none():
            return {"message": "Активная заявка на подтверждение уже существует", "created_count": 0}

        first_assignment = assignments[0]
        db.add(AssetConfirmation(
            asset_id=target_asset.asset_id,
            employee_id=request.employee_id,
            requested_by=requested_by,
            status=AssetConfirmationStatus.PENDING,
            comment=request.comment
        ))
        db.add(Notification(
            employee_id=request.employee_id,
            asset_id=target_asset.asset_id,
            event_type=NotificationEventType.CHECK_REQUIRE,
            initiator_id=requested_by,
            status=NotificationStatus.UNREAD,
            assignment_type=first_assignment.assignment_type
        ))
        created_count += 1

    # ==============================================================================
    # СЦЕНАРИЙ 2: Указан только employee_id (массовая заявка)
    # ==============================================================================
    elif request.employee_id and not target_asset:
        assignments = (await db.execute(select(AssetAssignment).where(
            AssetAssignment.employee_id == request.employee_id,
            AssetAssignment.end_date.is_(None)
        ))).scalars().all()

        assets_to_confirm = {}
        for assignment in assignments:
            if assignment.asset_id not in assets_to_confirm:
                assets_to_confirm[assignment.asset_id] = assignment

        for asset_id, first_assignment in assets_to_confirm.items():
            existing = await db.execute(select(AssetConfirmation).where(
                AssetConfirmation.asset_id == asset_id,
                AssetConfirmation.employee_id == request.employee_id,
                AssetConfirmation.status == AssetConfirmationStatus.PENDING
            ))
            if existing.scalar_one_or_none():
                continue

            db.add(AssetConfirmation(
                asset_id=asset_id,
                employee_id=request.employee_id,
                requested_by=requested_by,
                status=AssetConfirmationStatus.PENDING,
                comment=request.comment
            ))
            db.add(Notification(
                employee_id=request.employee_id,
                asset_id=asset_id,
                event_type=NotificationEventType.CHECK_REQUIRE,
                initiator_id=requested_by,
                status=NotificationStatus.UNREAD,
                assignment_type=first_assignment.assignment_type
            ))
            created_count += 1

    # ==============================================================================
    # СЦЕНАРИЙ 3: Указан только актив (для всех ответственных)
    # ==============================================================================
    elif target_asset and not request.employee_id:
        assignments = (await db.execute(select(AssetAssignment).where(
            AssetAssignment.asset_id == target_asset.asset_id,
            AssetAssignment.end_date.is_(None)
        ))).scalars().all()

        if not assignments:
            raise ValueError("У актива нет текущих ответственных сотрудников")

        employees_to_notify = {}
        for assignment in assignments:
            if assignment.employee_id not in employees_to_notify:
                employees_to_notify[assignment.employee_id] = assignment

        for employee_id, first_assignment in employees_to_notify.items():
            existing = await db.execute(select(AssetConfirmation).where(
                AssetConfirmation.asset_id == target_asset.asset_id,
                AssetConfirmation.employee_id == employee_id,
                AssetConfirmation.status == AssetConfirmationStatus.PENDING
            ))
            if existing.scalar_one_or_none():
                continue

            db.add(AssetConfirmation(
                asset_id=target_asset.asset_id,
                employee_id=employee_id,
                requested_by=requested_by,
                status=AssetConfirmationStatus.PENDING,
                comment=request.comment
            ))
            db.add(Notification(
                employee_id=employee_id,
                asset_id=target_asset.asset_id,
                event_type=NotificationEventType.CHECK_REQUIRE,
                initiator_id=requested_by,
                status=NotificationStatus.UNREAD,
                assignment_type=first_assignment.assignment_type
            ))
            created_count += 1

    await db.commit()
    return {"message": f"Создано {created_count} заявок на подтверждение", "created_count": created_count}


async def process_confirmation(
        db: AsyncSession,
        request: ConfirmAssetRequest,
        current_user_employee_id: str
) -> dict:
    """
    Обрабатывает подтверждение актива.
    Строго требует asset_id и сверяет inventory_id / serial_number, если они переданы.
    """
    # 1. Идентифицируем актив строго по asset_id
    result = await db.execute(select(Asset).where(Asset.asset_id == request.asset_id))
    asset = result.scalar_one_or_none()

    if not asset:
        raise ValueError(f"Актив с ID {request.asset_id} не найден")

    # 2. СТРОГАЯ ВАЛИДАЦИЯ: сверяем переданные значения с теми, что в БД
    # Если значение передано в запросе (не None), оно должно совпадать с БД.
    # Если в БД None, а в запросе None, условие != вернет False, и ошибка не выбросится (проверка пропущена).

    if request.inventory_id is not None and request.inventory_id != asset.inventory_id:
        raise ValueError(
            f"Несоответствие инвентарного номера. "
            f"В базе данных: '{asset.inventory_id}', в запросе: '{request.inventory_id}'"
        )

    if request.serial_number is not None and request.serial_number != asset.serial_number:
        raise ValueError(
            f"Несоответствие серийного номера. "
            f"В базе данных: '{asset.serial_number}', в запросе: '{request.serial_number}'"
        )

    # 3. Проверяем, что текущий пользователь действительно отвечает за этот актив
    assignment_stmt = select(AssetAssignment).where(
        AssetAssignment.asset_id == asset.asset_id,
        AssetAssignment.employee_id == current_user_employee_id,
        AssetAssignment.end_date.is_(None)
    )
    # Используем first(), так как привязок может быть несколько (user + serving)
    assignment = (await db.execute(assignment_stmt)).scalars().first()

    if not assignment:
        raise ValueError("Вы не числитесь ответственным за этот актив")

    # 4. Ищем СУЩЕСТВУЮЩИЙ запрос на подтверждение (строго PENDING)
    confirmation_stmt = select(AssetConfirmation).where(
        AssetConfirmation.asset_id == asset.asset_id,
        AssetConfirmation.employee_id == current_user_employee_id,
        AssetConfirmation.status == AssetConfirmationStatus.PENDING
    ).order_by(AssetConfirmation.created_at.desc())

    confirmation = (await db.execute(confirmation_stmt)).scalar_one_or_none()

    # === ГЛАВНОЕ ИЗМЕНЕНИЕ: Если заявки нет, выбрасываем ошибку ===
    if not confirmation:
        raise ValueError(
            f"У вас нет активной заявки на подтверждение наличия актива '{asset.name}'. "
            f"Обратитесь к администратору для создания заявки."
        )

    # 5. Обновляем существующую заявку
    confirmation.status = request.status
    confirmation.comment = request.comment or confirmation.comment
    confirmation.confirmed_at = datetime.now()

    await db.commit()

    return {
        "message": f"Статус актива '{asset.name}' успешно обновлен: {AssetConfirmationStatus.get_ru_label(status=request.status)}",
        "asset_id": asset.asset_id,
        "asset_name": asset.name,
        "inventory_id": asset.inventory_id,
        "serial_number": asset.serial_number,
        "status": request.status
    }


async def get_confirmations_list(
        db: AsyncSession,
        asset_id: Optional[int] = None,
        employee_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
) -> dict:
    """Получить список запросов на подтверждение с фильтрами и обогащенными данными"""
    data_query = (
        select(
            AssetConfirmation,
            Asset.name.label('asset_name'),
            Employee.last_name,
            Employee.first_name,
            Employee.middle_name
        )
        .join(Asset, AssetConfirmation.asset_id == Asset.asset_id, isouter=True)
        .join(Employee, AssetConfirmation.employee_id == Employee.employee_id, isouter=True)
    )

    count_query = select(func.count(AssetConfirmation.id))

    filters = []
    if asset_id is not None:
        filters.append(AssetConfirmation.asset_id == asset_id)
    if employee_id is not None:
        filters.append(AssetConfirmation.employee_id == employee_id)
    if status is not None:
        filters.append(AssetConfirmation.status == status)

    if filters:
        data_query = data_query.where(and_(*filters))
        count_query = count_query.select_from(AssetConfirmation).where(and_(*filters))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    skip = (page - 1) * page_size
    data_query = data_query.order_by(AssetConfirmation.created_at.desc()).offset(skip).limit(page_size)
    result = await db.execute(data_query)
    rows = result.all()

    items = []
    for row in rows:
        conf = row.AssetConfirmation
        parts = [p for p in [row.last_name, row.first_name, row.middle_name] if p]
        employee_full_name = " ".join(parts) if parts else None
        requested_full_name = await get_employee_full_name(db=db, employee_id=conf.requested_by)
        items.append({
            "id": conf.id,
            "asset_id": conf.asset_id,
            "asset_name": row.asset_name,
            "employee_id": conf.employee_id,
            "employee_full_name": employee_full_name,
            "requested_by": conf.requested_by,
            "requested_full_name": requested_full_name,
            "status": conf.status,
            "status_ru": conf.status_ru,
            "comment": conf.comment,
            "created_at": conf.created_at,
            "confirmed_at": conf.confirmed_at
        })

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1
    }


async def get_last_confirmation(
        db: AsyncSession,
        asset_id: int,
        employee_id: Optional[str] = None
) -> Optional[dict]:
    """
    Получить последнюю запись по времени создания.
    """
    query = (
        select(
            AssetConfirmation,
            Asset.name.label('asset_name'),
            Employee.last_name,
            Employee.first_name,
            Employee.middle_name
        )
        .join(Asset, AssetConfirmation.asset_id == Asset.asset_id, isouter=True)
        .join(Employee, AssetConfirmation.employee_id == Employee.employee_id, isouter=True)
        .where(AssetConfirmation.asset_id == asset_id)
    )

    if employee_id is not None:
        query = query.where(AssetConfirmation.employee_id == employee_id)

    # query = query.order_by(AssetConfirmation.confirmed_at.desc().nullslast())
    query = query.order_by(AssetConfirmation.created_at.desc())
    query = query.limit(1)

    result = await db.execute(query)
    row = result.first()

    if not row:
        return None

    conf = row.AssetConfirmation
    parts = [p for p in [row.last_name, row.first_name, row.middle_name] if p]
    employee_full_name = " ".join(parts) if parts else None
    requested_full_name = await get_employee_full_name(db=db, employee_id=conf.requested_by)

    return {
        "id": conf.id,
        "asset_id": conf.asset_id,
        "asset_name": row.asset_name,
        "employee_id": conf.employee_id,
        "employee_full_name": employee_full_name,
        "requested_by": conf.requested_by,
        "requested_full_name": requested_full_name,
        "status": conf.status,
        "status_ru": conf.status_ru,
        "comment": conf.comment,
        "created_at": conf.created_at,
        "confirmed_at": conf.confirmed_at
    }