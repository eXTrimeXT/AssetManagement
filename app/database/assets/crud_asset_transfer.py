from datetime import date, datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.assets.Asset import Asset
from app.models.assets.AssetAssignment import AssetAssignment
from app.models.notifications.Notification import Notification, NotificationEventType, NotificationStatus
from app.schemas.assets.AssetTransferSchemas import AssetTransferRequest, SapAssetCreateRequest

async def create_asset_from_sap(db: AsyncSession, sap_data: SapAssetCreateRequest, created_by: str) -> Asset:
    new_asset = Asset(
        inventory_id=sap_data.inventory_id,
        name=sap_data.name,
        serial_number=sap_data.serial_number,
        asset_type_id=sap_data.asset_type_id,
        model_id=sap_data.model_id,
        asset_status_id=sap_data.asset_status_id,
        quantity=sap_data.quantity,
        created_by=created_by,
        updated_by=created_by
    )
    db.add(new_asset)
    await db.commit()
    await db.refresh(new_asset)
    return new_asset

async def request_asset_transfer(
        db: AsyncSession,
        request: AssetTransferRequest,
        initiator_id: str
) -> Notification:
    # 1. Если передан SAP-актив, создаем его локально
    asset_id = request.asset_id
    if request.sap_asset:
        try:
            new_asset = await create_asset_from_sap(db, request.sap_asset, initiator_id)
            asset_id = new_asset.asset_id
        except IntegrityError:
            await db.rollback()
            raise ValueError("Актив с таким inventory_id уже существует локально")

    # 2. Создаем уведомление для получателя
    notification = Notification(
        employee_id=request.target_employee_id,
        asset_id=asset_id,
        event_type=NotificationEventType.TRANSFER_ASSET_INIT,
        initiator_id=initiator_id,
        status=NotificationStatus.UNREAD,
        assignment_type=request.assignment_type
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    return notification

async def respond_to_asset_transfer(
        db: AsyncSession,
        notification_id: int,
        action: str,
        responder_id: str,
        comment: Optional[str] = None
) -> dict:
    result = await db.execute(
        select(Notification).where(Notification.notification_id == notification_id)
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise ValueError("Уведомление не найдено")
    if notification.employee_id != responder_id:
        raise ValueError("Вы не являетесь получателем этого уведомления")
    if notification.status != NotificationStatus.UNREAD:
        raise ValueError("На это уведомление уже был дан ответ")

    asset_id = notification.asset_id
    initiator_id = notification.initiator_id
    assignment_type = notification.assignment_type or "user"

    # Помечаем текущее уведомление как обработанное
    notification.status = NotificationStatus.READ
    notification.responded_at = datetime.utcnow()

    if action == "decline":
        # Уведомляем инициатора об отказе
        decline_notification = Notification(
            employee_id=initiator_id,
            asset_id=asset_id,
            event_type=NotificationEventType.TRANSFER_ASSET_DECLINED,
            initiator_id=responder_id,
            status=NotificationStatus.UNREAD,
            assignment_type=assignment_type
        )
        db.add(decline_notification)
        response_msg = "Передача актива отклонена"

    elif action == "accept":
        # 1. Отвязываем текущий актив (если есть активная привязка данного типа)
        active_assignment_result = await db.execute(
            select(AssetAssignment).where(
                AssetAssignment.asset_id == asset_id,
                AssetAssignment.assignment_type == assignment_type,
                AssetAssignment.end_date.is_(None)
            )
        )
        active_assignment = active_assignment_result.scalar_one_or_none()

        if active_assignment:
            active_assignment.end_date = date.today()

        # 2. Создаем новую привязку для получателя (того, кто принял)
        new_assignment = AssetAssignment(
            asset_id=asset_id,
            employee_id=responder_id,
            assignment_type=assignment_type,
            start_date=date.today(),
            end_date=None,
            assigned_by=initiator_id,
            comment=comment
        )
        db.add(new_assignment)

        # 3. Уведомляем инициатора об успехе
        accept_notification = Notification(
            employee_id=initiator_id,
            asset_id=asset_id,
            event_type=NotificationEventType.TRANSFER_ASSET_ACCEPTED,
            initiator_id=responder_id,
            status=NotificationStatus.UNREAD,
            assignment_type=assignment_type
        )
        db.add(accept_notification)
        response_msg = "Передача актива успешно завершена"
    else:
        raise ValueError("Недопустимое действие")

    await db.commit()
    return {"message": response_msg, "notification": notification}