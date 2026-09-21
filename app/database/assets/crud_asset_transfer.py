import logging
from datetime import date, datetime
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.assets.Asset import Asset
from app.models.assets.AssetAssignment import AssetAssignment
from app.models.zup.employee import Employee
from app.models.notifications.Notification import Notification, NotificationEventType, NotificationStatus
from app.schemas.assets.AssetTransferSchemas import (
    AssetTransferRequest,
    AssetTransferResponse,
    AssetTransferRespondResponse,
    AssetInfoResponse,
    EmployeeInfoResponse,
    NotificationInfoResponse
)
from app.services.assets.asset_list_service import fetch_sap_materials

logger = logging.getLogger(__name__)

async def get_employee_full_name(db: AsyncSession, employee_id: str) -> Optional[str]:
    result = await db.execute(select(Employee).where(Employee.employee_id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        return None
    parts = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
    return " ".join(parts) if parts else None

async def fetch_sap_asset_data_for_transfer(db: AsyncSession, material_id: str) -> Dict[str, Any]:
    """
    Получает данные ОДНОГО актива из SAP API по material_id.
    """
    try:
        sap_response = await fetch_sap_materials(
            page=1,
            page_size=1,
            material_id=material_id,
            search_mode="ALL",
        )

        if not sap_response.get("success") or "data" not in sap_response.get("response", {}):
            raise ValueError(f"Актив с material_id '{material_id}' не найден в SAP API")

        sap_data_list = sap_response["response"]["data"]
        if not sap_data_list:
            raise ValueError(f"Актив с material_id '{material_id}' не найден в SAP API (пустой список)")

        sap_item = sap_data_list[0]

        # Извлекаем и форматируем employee_id из SAP (приводим к строке и дополняем нулями до 10 символов, если нужно)
        raw_emp_id = sap_item.get("employee_id")
        sap_employee_id = str(raw_emp_id).zfill(10) if raw_emp_id else None

        return {
            "material_id": sap_item.get("material_id", material_id),
            "inventory_id": sap_item.get("inventory_number", material_id),
            "name": sap_item.get("base_material_name", f"Актив SAP {material_id}"),
            "serial_number": sap_item.get("serial_number"),
            "quantity": int(sap_item.get("quantity", 1)) if sap_item.get("quantity") is not None else 1,
            "every_week_check": False,
            "asset_type_id": 10,
            "asset_status_id": 9,
            "model_id": None,
            # Добавляем данные для привязки пользователя
            "sap_employee_id": sap_employee_id,
            "changed_date": sap_item.get("changed_date")
        }

    except Exception as exc:
        logger.error(f"Ошибка при получении данных SAP для transfer (material_id={material_id}): {exc}")
        raise ValueError(f"Не удалось получить данные актива из SAP: {exc}")


async def create_asset_from_sap_material(db: AsyncSession, material_id: str, created_by: str) -> Asset:
    """
    Создает локальную запись актива на основе данных из SAP и сразу создает привязку пользователя, если она есть в SAP.
    """
    sap_data = await fetch_sap_asset_data_for_transfer(db, material_id)

    new_asset = Asset(
        material_id=sap_data["material_id"],
        inventory_id=sap_data["inventory_id"],
        name=sap_data["name"],
        serial_number=sap_data.get("serial_number"),
        asset_type_id=sap_data["asset_type_id"],
        model_id=sap_data.get("model_id"),
        asset_status_id=sap_data["asset_status_id"],
        quantity=sap_data["quantity"],
        every_week_check=sap_data["every_week_check"],
        created_by=created_by,
        updated_by=created_by
    )

    db.add(new_asset)

    # ВАЖНО: Делаем flush, чтобы база данных сгенерировала new_asset.asset_id до коммита
    await db.flush()

    # Если в SAP указан сотрудник, создаем для него начальную привязку
    if sap_data.get("sap_employee_id"):
        # Парсим дату начала привязки из SAP (формат YYYYMMDD)
        start_date = date.today()
        changed_date_str = sap_data.get("changed_date")
        if changed_date_str and len(str(changed_date_str)) == 8:
            try:
                start_date = datetime.strptime(str(changed_date_str), "%Y%m%d").date()
            except ValueError:
                pass  # Если дата некорректна, используем сегодняшнюю

        new_assignment = AssetAssignment(
            asset_id=new_asset.asset_id,
            employee_id=sap_data["sap_employee_id"],
            assignment_type="user",  # По умолчанию назначаем как пользователя
            start_date=start_date,
            end_date=None,
            assigned_by=created_by,
            comment="Автоматическая привязка при импорте из SAP"
        )
        db.add(new_assignment)

    # Финальный коммит для актива и привязки
    await db.commit()
    await db.refresh(new_asset)
    return new_asset

async def request_asset_transfer(
        db: AsyncSession,
        request: AssetTransferRequest,
        initiator_id: str
) -> AssetTransferResponse:
    asset_id = request.asset_id
    asset_source = "local"

    if request.material_id:
        try:
            new_asset = await create_asset_from_sap_material(db, request.material_id, initiator_id)
            asset_id = new_asset.asset_id
            asset_source = "sap"
        except IntegrityError:
            await db.rollback()
            raise ValueError(f"Актив с material_id={request.material_id} не привязан к вам!")

    result = await db.execute(select(Asset).where(Asset.asset_id == asset_id))
    asset = result.scalar_one()

    initiator_name = await get_employee_full_name(db, initiator_id)
    target_name = await get_employee_full_name(db, request.target_employee_id)

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

    assignment_type_ru = "Пользователь" if request.assignment_type == "user" else "Ответственный"

    return AssetTransferResponse(
        message="Запрос на передачу актива успешно создан",
        action="transfer_initiated",
        notification=NotificationInfoResponse(
            notification_id=notification.notification_id,
            event_type=notification.event_type,
            event_type_ru="Инициация передачи актива",
            status=notification.status,
            created_at=notification.created_at
        ),
        asset=AssetInfoResponse(
            asset_id=asset.asset_id,
            inventory_id=asset.inventory_id,
            name=asset.name,
            serial_number=asset.serial_number,
            asset_type_id=asset.asset_type_id,
            model_id=asset.model_id,
            source=asset_source
        ),
        initiator=EmployeeInfoResponse(employee_id=initiator_id, full_name=initiator_name),
        target_employee=EmployeeInfoResponse(employee_id=request.target_employee_id, full_name=target_name),
        assignment_type=request.assignment_type,
        assignment_type_ru=assignment_type_ru,
        comment=request.comment,
        created_at=notification.created_at
    )

async def respond_to_asset_transfer(
        db: AsyncSession,
        notification_id: int,
        action: str,
        responder_id: str,
        comment: Optional[str] = None
) -> AssetTransferRespondResponse:
    result = await db.execute(select(Notification).where(Notification.notification_id == notification_id))
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

    asset_result = await db.execute(select(Asset).where(Asset.asset_id == asset_id))
    asset = asset_result.scalar_one()

    initiator_name = await get_employee_full_name(db, initiator_id)
    responder_name = await get_employee_full_name(db, responder_id)

    notification.status = NotificationStatus.READ
    notification.responded_at = datetime.utcnow()

    assignment_type_ru = "Пользователь" if assignment_type == "user" else "Ответственный"
    new_assignment_id = None
    previous_assignment_closed = False

    if action == "decline":
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
        response_notification = decline_notification

    elif action == "accept":
        # Отвязываем текущий актив (это закроет и ту привязку, которую мы только что создали из SAP, если она была)
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
            previous_assignment_closed = True

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
        response_notification = accept_notification
    else:
        raise ValueError("Недопустимое действие")

    await db.commit()
    await db.refresh(response_notification)

    if action == "accept":
        new_assignment_result = await db.execute(
            select(AssetAssignment).where(
                AssetAssignment.asset_id == asset_id,
                AssetAssignment.employee_id == responder_id,
                AssetAssignment.assignment_type == assignment_type,
                AssetAssignment.end_date.is_(None)
            ).order_by(AssetAssignment.id.desc())
        )
        new_assignment_obj = new_assignment_result.scalars().first()
        if new_assignment_obj:
            new_assignment_id = new_assignment_obj.id

    event_type_ru_map = {
        NotificationEventType.TRANSFER_ASSET_DECLINED: "Передача актива отклонена",
        NotificationEventType.TRANSFER_ASSET_ACCEPTED: "Передача актива принята"
    }

    return AssetTransferRespondResponse(
        message=response_msg,
        action=action,
        notification=NotificationInfoResponse(
            notification_id=response_notification.notification_id,
            event_type=response_notification.event_type,
            event_type_ru=event_type_ru_map.get(response_notification.event_type, "Ответ на передачу"),
            status=response_notification.status,
            created_at=response_notification.created_at
        ),
        asset=AssetInfoResponse(
            asset_id=asset.asset_id,
            inventory_id=asset.inventory_id,
            name=asset.name,
            serial_number=asset.serial_number,
            asset_type_id=asset.asset_type_id,
            model_id=asset.model_id,
            source="local"
        ),
        initiator=EmployeeInfoResponse(employee_id=initiator_id, full_name=initiator_name),
        responder=EmployeeInfoResponse(employee_id=responder_id, full_name=responder_name),
        assignment_type=assignment_type,
        assignment_type_ru=assignment_type_ru,
        comment=comment,
        responded_at=notification.responded_at,
        new_assignment_id=new_assignment_id,
        previous_assignment_closed=previous_assignment_closed
    )