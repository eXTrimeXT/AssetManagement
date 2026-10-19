import json
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
        material_id: Optional[str] = None,
        serial_number: Optional[str] = None,
        inventory_id: Optional[str] = None
) -> Optional[Asset]:
    """
    Поиск актива по одному из идентификаторов.
    Приоритет:
    1. asset_id (точный поиск)
    2. material_id (точный поиск)
    3. serial_number и/или inventory_id (поиск через OR)
    """
    # 1. Прямой поиск по asset_id
    if asset_id:
        result = await db.execute(select(Asset).where(Asset.asset_id == asset_id))
        return result.scalar_one_or_none()

    # 2. Поиск по material_id
    if material_id:
        result = await db.execute(select(Asset).where(Asset.material_id == material_id))
        return result.scalar_one_or_none()

    # 3. Поиск по serial_number и/или inventory_id
    if serial_number or inventory_id:
        conditions = []
        if serial_number:
            conditions.append(Asset.serial_number == serial_number.strip())
        if inventory_id:
            conditions.append(Asset.inventory_id == inventory_id.strip())

        result = await db.execute(select(Asset).where(or_(*conditions)))
        return result.scalar_one_or_none()

    return None

async def create_confirmation_request(
        db: AsyncSession,
        request: CreateConfirmationRequest,
        requested_by: str
) -> dict:
    """
    Создает заявку на подтверждение и отправляет уведомления.
    Логика:
    - Если указаны И employee_id, И (asset_id или material_id) — создаем заявку ТОЛЬКО
      для этого сотрудника и ТОЛЬКО на этот актив.
    - Если указан только employee_id — создаем заявки на ВСЕ активы сотрудника.
    - Если указан только asset_id или material_id — создаем заявки для ВСЕХ текущих
      ответственных за этот актив.
    """
    created_count = 0

    # Определяем, указан ли конкретный актив
    target_asset = None
    if request.asset_id or request.material_id:
        target_asset = await _get_asset_by_identifiers(
            db, asset_id=request.asset_id, material_id=request.material_id
        )
        if not target_asset:
            raise ValueError("Актив не найден по указанным данным")

    # ==============================================================================
    # СЦЕНАРИЙ 1: Указаны И сотрудник, И конкретный актив
    # Создаем заявку ТОЛЬКО для этого сотрудника и ТОЛЬКО на этот актив
    # ==============================================================================
    if request.employee_id and target_asset:
        # ИСПРАВЛЕНИЕ: используем all() вместо scalar_one_or_none(),
        # так как у сотрудника может быть несколько привязок (user, serving и т.д.)
        assignment_stmt = select(AssetAssignment).where(
            AssetAssignment.asset_id == target_asset.asset_id,
            AssetAssignment.employee_id == request.employee_id,
            AssetAssignment.end_date.is_(None)
        )
        assignments_result = await db.execute(assignment_stmt)
        assignments = assignments_result.scalars().all()

        if not assignments:
            raise ValueError(
                f"Сотрудник {request.employee_id} не числится ответственным за актив {target_asset.asset_id}"
            )

        # Проверяем, нет ли уже активной заявки
        existing = await db.execute(select(AssetConfirmation).where(
            AssetConfirmation.asset_id == target_asset.asset_id,
            AssetConfirmation.employee_id == request.employee_id,
            AssetConfirmation.status == AssetConfirmationStatus.PENDING
        ))
        if existing.scalar_one_or_none():
            return {
                "message": "Активная заявка на подтверждение уже существует",
                "created_count": 0
            }

        # Берем первую привязку для определения assignment_type уведомления
        first_assignment = assignments[0]

        confirmation = AssetConfirmation(
            asset_id=target_asset.asset_id,
            employee_id=request.employee_id,
            requested_by=requested_by,
            status=AssetConfirmationStatus.PENDING,
            comment=request.comment
        )
        db.add(confirmation)

        # Создаем ОДНО уведомление для сотрудника (не по каждой привязке, чтобы не спамить)
        notification = Notification(
            employee_id=request.employee_id,
            asset_id=target_asset.asset_id,
            event_type=NotificationEventType.CHECK_REQUIRE,
            initiator_id=requested_by,
            status=NotificationStatus.UNREAD,
            assignment_type=first_assignment.assignment_type
        )
        db.add(notification)
        created_count += 1

    # ==============================================================================
    # СЦЕНАРИЙ 2: Указан только employee_id (без актива)
    # Создаем заявки на ВСЕ активы сотрудника
    # ==============================================================================
    elif request.employee_id and not target_asset:
        assignments_stmt = select(AssetAssignment).where(
            AssetAssignment.employee_id == request.employee_id,
            AssetAssignment.end_date.is_(None)
        )
        assignments = (await db.execute(assignments_stmt)).scalars().all()

        # Группируем привязки по asset_id, чтобы не создавать дубликаты заявок
        # (у сотрудника может быть несколько привязок к одному активу: user + serving)
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

            confirmation = AssetConfirmation(
                asset_id=asset_id,
                employee_id=request.employee_id,
                requested_by=requested_by,
                status=AssetConfirmationStatus.PENDING,
                comment=request.comment
            )
            db.add(confirmation)

            notification = Notification(
                employee_id=request.employee_id,
                asset_id=asset_id,
                event_type=NotificationEventType.CHECK_REQUIRE,
                initiator_id=requested_by,
                status=NotificationStatus.UNREAD,
                assignment_type=first_assignment.assignment_type
            )
            db.add(notification)
            created_count += 1

    # ==============================================================================
    # СЦЕНАРИЙ 3: Указан только актив (asset_id или material_id)
    # Создаем заявки для ВСЕХ текущих ответственных за этот актив
    # ==============================================================================
    elif target_asset and not request.employee_id:
        assignments_stmt = select(AssetAssignment).where(
            AssetAssignment.asset_id == target_asset.asset_id,
            AssetAssignment.end_date.is_(None)
        )
        assignments = (await db.execute(assignments_stmt)).scalars().all()

        if not assignments:
            raise ValueError("У актива нет текущих ответственных сотрудников")

        # Группируем по employee_id, чтобы не создавать дубликаты
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

            confirmation = AssetConfirmation(
                asset_id=target_asset.asset_id,
                employee_id=employee_id,
                requested_by=requested_by,
                status=AssetConfirmationStatus.PENDING,
                comment=request.comment
            )
            db.add(confirmation)

            notification = Notification(
                employee_id=employee_id,
                asset_id=target_asset.asset_id,
                event_type=NotificationEventType.CHECK_REQUIRE,
                initiator_id=requested_by,
                status=NotificationStatus.UNREAD,
                assignment_type=first_assignment.assignment_type
            )
            db.add(notification)
            created_count += 1

    await db.commit()
    return {
        "message": f"Создано {created_count} заявок на подтверждение",
        "created_count": created_count
    }


async def process_confirmation(
        db: AsyncSession,
        request: ConfirmAssetRequest,
        current_user_employee_id: str
) -> dict:
    """
    Обрабатывает подтверждение актива.
    Актив идентифицируется по asset_id, serial_number и/или inventory_id.
    """
    # 1. Идентифицируем актив
    asset = await _get_asset_by_identifiers(
        db,
        asset_id=request.asset_id,
        serial_number=request.serial_number,
        inventory_id=request.inventory_id
    )

    if not asset:
        # Формируем понятное сообщение об ошибке
        identifiers = []
        if request.asset_id:
            identifiers.append(f"asset_id={request.asset_id}")
        if request.serial_number:
            identifiers.append(f"serial_number='{request.serial_number}'")
        if request.inventory_id:
            identifiers.append(f"inventory_id='{request.inventory_id}'")
        raise ValueError(f"Актив не найден по указанным данным ({', '.join(identifiers)})")

    # 2. Проверяем, что текущий пользователь действительно отвечает за этот актив
    assignment_stmt = select(AssetAssignment).where(
        AssetAssignment.asset_id == asset.asset_id,
        AssetAssignment.employee_id == current_user_employee_id,
        AssetAssignment.end_date.is_(None)
    )
    assignment = (await db.execute(assignment_stmt)).scalars().first()

    if not assignment:
        raise ValueError("Вы не числитесь ответственным за этот актив")

    # 3. Ищем существующий запрос на подтверждение (если он был создан)
    confirmation_stmt = select(AssetConfirmation).where(
        AssetConfirmation.asset_id == asset.asset_id,
        AssetConfirmation.employee_id == current_user_employee_id,
        AssetConfirmation.status == AssetConfirmationStatus.PENDING
    ).order_by(AssetConfirmation.created_at.desc())

    confirmation = (await db.execute(confirmation_stmt)).scalar_one_or_none()

    if confirmation:
        # Обновляем существующий запрос
        confirmation.status = request.status
        confirmation.comment = request.comment or confirmation.comment
        confirmation.confirmed_at = datetime.now()
    else:
        # Если запроса не было, создаем запись о факте подтверждения "задним числом"
        confirmation = AssetConfirmation(
            asset_id=asset.asset_id,
            employee_id=current_user_employee_id,
            requested_by=current_user_employee_id,  # Сам инициировал и подтвердил
            status=request.status,
            comment=request.comment or "Подтверждено без предварительного запроса",
            confirmed_at=datetime.now()
        )
        db.add(confirmation)

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


# ==============================================================================
# НОВАЯ ФУНКЦИЯ: Получение последней записи о подтверждении актива
# ==============================================================================
async def get_last_confirmation(
        db: AsyncSession,
        asset_id: int,
        employee_id: Optional[str] = None
) -> Optional[dict]:
    """
    Получить последнюю запись о подтверждении наличия актива.

    - Если указан employee_id — возвращает последнее подтверждение именно этого сотрудника.
    - Если employee_id не указан — возвращает последнее подтверждение ЛЮБОГО сотрудника.

    Возвращает None, если записей нет.
    """
    # Базовый запрос с JOIN для обогащения данных
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

    query = query.order_by(AssetConfirmation.confirmed_at.desc().nullslast())
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