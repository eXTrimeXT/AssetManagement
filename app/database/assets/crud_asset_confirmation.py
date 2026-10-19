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
from app.models.notifications.Notification import Notification, NotificationStatus
from app.schemas.assets.AssetConfirmationSchemas import CreateConfirmationRequest, ConfirmAssetRequest
from app.models.zup import Employee

logger = logging.getLogger(__name__)

async def _get_asset_by_identifiers(db: AsyncSession, asset_id: Optional[int] = None, material_id: Optional[str] = None, qr_data: Optional[str] = None) -> Optional[Asset]:
    """Поиск актива по ID, material_id или данным из QR-кода"""
    if asset_id:
        result = await db.execute(select(Asset).where(Asset.asset_id == asset_id))
        return result.scalar_one_or_none()

    if material_id:
        result = await db.execute(select(Asset).where(Asset.material_id == material_id))
        return result.scalar_one_or_none()

    if qr_data:
        # Попытка распарсить JSON из QR-кода
        try:
            qr_dict = json.loads(qr_data)
            inv_id = qr_dict.get("inventory_id")
            sn = qr_dict.get("serial_number")

            conditions = []
            if inv_id: conditions.append(Asset.inventory_id == inv_id)
            if sn: conditions.append(Asset.serial_number == sn)

            if conditions:
                result = await db.execute(select(Asset).where(or_(*conditions)))
                asset = result.scalar_one_or_none()
                if asset: return asset
        except json.JSONDecodeError:
            # Если не JSON, пробуем искать как по инвентарному или серийному номеру напрямую
            result = await db.execute(
                select(Asset).where(
                    or_(
                        Asset.inventory_id == qr_data.strip(),
                        Asset.serial_number == qr_data.strip()
                    )
                )
            )
            return result.scalar_one_or_none()

    return None

async def create_confirmation_request(
        db: AsyncSession,
        request: CreateConfirmationRequest,
        requested_by: str
) -> dict:
    """Создает заявку на подтверждение и отправляет уведомления"""
    created_count = 0

    # Сценарий 1: Массовый запрос по сотруднику
    if request.employee_id:
        # Находим все активные привязки сотрудника
        assignments_stmt = select(AssetAssignment).where(
            AssetAssignment.employee_id == request.employee_id,
            AssetAssignment.end_date.is_(None)
        )
        assignments = (await db.execute(assignments_stmt)).scalars().all()

        for assignment in assignments:
            # Проверяем, нет ли уже активного запроса
            existing = await db.execute(select(AssetConfirmation).where(
                AssetConfirmation.asset_id == assignment.asset_id,
                AssetConfirmation.employee_id == request.employee_id,
                AssetConfirmation.status == AssetConfirmationStatus.PENDING
            ))
            if existing.scalar_one_or_none():
                continue

            confirmation = AssetConfirmation(
                asset_id=assignment.asset_id,
                employee_id=request.employee_id,
                requested_by=requested_by,
                status=AssetConfirmationStatus.PENDING,
                comment=request.comment
            )
            db.add(confirmation)
            created_count += 1

    # Сценарий 2: Запрос по конкретному активу (asset_id или material_id)
    else:
        asset = await _get_asset_by_identifiers(db, asset_id=request.asset_id, material_id=request.material_id)
        if not asset:
            raise ValueError("Актив не найден")

        # Находим всех текущих ответственных за этот актив
        assignments_stmt = select(AssetAssignment).where(
            AssetAssignment.asset_id == asset.asset_id,
            AssetAssignment.end_date.is_(None)
        )
        assignments = (await db.execute(assignments_stmt)).scalars().all()

        if not assignments:
            raise ValueError("У актива нет текущих ответственных сотрудников")

        for assignment in assignments:
            confirmation = AssetConfirmation(
                asset_id=asset.asset_id,
                employee_id=assignment.employee_id,
                requested_by=requested_by,
                status=AssetConfirmationStatus.PENDING,
                comment=request.comment
            )
            db.add(confirmation)

            # Создаем уведомление для сотрудника
            notification = Notification(
                employee_id=assignment.employee_id,
                asset_id=asset.asset_id,
                event_type="CONFIRMATION_REQUEST", # Убедитесь, что этот тип добавлен в NotificationEventType или используйте строку
                initiator_id=requested_by,
                status=NotificationStatus.UNREAD,
                assignment_type=assignment.assignment_type
            )
            db.add(notification)
            created_count += 1

    await db.commit()
    return {"message": f"Создано {created_count} заявок на подтверждение", "created_count": created_count}


async def process_confirmation(
        db: AsyncSession,
        request: ConfirmAssetRequest,
        current_user_employee_id: str
) -> dict:
    """Обрабатывает подтверждение актива (через QR или прямой ID)"""
    # 1. Идентифицируем актив
    asset = await _get_asset_by_identifiers(
        db,
        asset_id=request.asset_id,
        qr_data=request.qr_data
    )

    if not asset:
        raise ValueError("Актив не найден по предоставленным данным или QR-коду")

    # 2. Проверяем, что текущий пользователь действительно отвечает за этот актив
    assignment_stmt = select(AssetAssignment).where(
        AssetAssignment.asset_id == asset.asset_id,
        AssetAssignment.employee_id == current_user_employee_id,
        AssetAssignment.end_date.is_(None)
    )
    assignment = (await db.execute(assignment_stmt)).scalar_one_or_none()

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
        confirmation.confirmed_at = datetime.utcnow()
    else:
        # Если запроса не было, создаем запись о факте подтверждения "задним числом"
        confirmation = AssetConfirmation(
            asset_id=asset.asset_id,
            employee_id=current_user_employee_id,
            requested_by=current_user_employee_id, # Сам инициировал и подтвердил
            status=request.status,
            comment=request.comment or "Подтверждено без предварительного запроса",
            confirmed_at=datetime.utcnow()
        )
        db.add(confirmation)

    # 4. Если актив не найден или поврежден, можно создать уведомление для админа (опционально)
    if request.status in ["not_found", "damaged"]:
        # Здесь можно добавить логику отправки уведомления создателю заявки или в IT-отдел
        pass

    await db.commit()

    return {
        "message": f"Статус актива '{asset.name}' успешно обновлен: {AssetConfirmationStatus.get_ru_label(status=request.status)}",
        "asset_name": asset.name,
        "inventory_id": asset.inventory_id,
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

    # Базовый запрос для получения данных с JOIN для избежания N+1
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

    # Базовый запрос для подсчета общего количества
    count_query = select(func.count(AssetConfirmation.id))

    # Применяем фильтры
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

    # 1. Получаем общее количество
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 2. Рассчитываем skip и получаем данные с пагинацией
    skip = (page - 1) * page_size
    data_query = data_query.order_by(AssetConfirmation.created_at.desc()).offset(skip).limit(page_size)
    result = await db.execute(data_query)
    rows = result.all()

    # 3. Формируем список элементов
    items = []
    for row in rows:
        conf = row.AssetConfirmation
        parts = [p for p in [row.last_name, row.first_name, row.middle_name] if p]
        full_name = " ".join(parts) if parts else None

        items.append({
            "id": conf.id,
            "asset_id": conf.asset_id,
            "asset_name": row.asset_name,
            "employee_id": conf.employee_id,
            "employee_full_name": full_name,
            "requested_by": conf.requested_by,
            "status": conf.status,
            "status_ru": conf.status_ru,
            "comment": conf.comment,
            "created_at": conf.created_at,
            "confirmed_at": conf.confirmed_at
        })

    # 4. Рассчитываем метаданные пагинации
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