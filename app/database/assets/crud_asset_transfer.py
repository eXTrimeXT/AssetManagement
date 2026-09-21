# from datetime import date, datetime
# from typing import Optional
# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.exc import IntegrityError
#
# from app.models.assets.Asset import Asset
# from app.models.assets.AssetAssignment import AssetAssignment
# from app.models.zup.employee import Employee
# from app.models.notifications.Notification import Notification, NotificationEventType, NotificationStatus
# from app.schemas.assets.AssetTransferSchemas import (
#     AssetTransferRequest,
#     SapAssetCreateRequest,
#     AssetTransferResponse,
#     AssetTransferRespondResponse,
#     AssetInfoResponse,
#     EmployeeInfoResponse,
#     NotificationInfoResponse
# )
#
# async def get_employee_full_name(db: AsyncSession, employee_id: str) -> Optional[str]:
#     """Получить полное имя сотрудника"""
#     result = await db.execute(
#         select(Employee).where(Employee.employee_id == employee_id)
#     )
#     employee = result.scalar_one_or_none()
#     if not employee:
#         return None
#     parts = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
#     return " ".join(parts) if parts else None
#
# async def create_asset_from_sap(db: AsyncSession, sap_data: SapAssetCreateRequest, created_by: str) -> Asset:
#     new_asset = Asset(
#         inventory_id=sap_data.inventory_id,
#         name=sap_data.name,
#         serial_number=sap_data.serial_number,
#         asset_type_id=sap_data.asset_type_id,
#         model_id=sap_data.model_id,
#         asset_status_id=sap_data.asset_status_id,
#         quantity=sap_data.quantity,
#         created_by=created_by,
#         updated_by=created_by
#     )
#     db.add(new_asset)
#     await db.commit()
#     await db.refresh(new_asset)
#     return new_asset
#
# async def request_asset_transfer(
#         db: AsyncSession,
#         request: AssetTransferRequest,
#         initiator_id: str
# ) -> AssetTransferResponse:
#     """
#     Создать запрос на передачу актива и вернуть подробный ответ
#     """
#     # 1. Определяем источник актива и получаем/создаем его
#     asset_id = request.asset_id
#     asset_source = "local"
#
#     if request.sap_asset:
#         try:
#             new_asset = await create_asset_from_sap(db, request.sap_asset, initiator_id)
#             asset_id = new_asset.asset_id
#             asset_source = "sap"
#         except IntegrityError:
#             await db.rollback()
#             raise ValueError("Актив с таким inventory_id уже существует локально")
#
#     # 2. Получаем информацию об активе
#     result = await db.execute(select(Asset).where(Asset.asset_id == asset_id))
#     asset = result.scalar_one()
#
#     # 3. Получаем имена участников
#     initiator_name = await get_employee_full_name(db, initiator_id)
#     target_name = await get_employee_full_name(db, request.target_employee_id)
#
#     # 4. Создаем уведомление для получателя
#     notification = Notification(
#         employee_id=request.target_employee_id,
#         asset_id=asset_id,
#         event_type=NotificationEventType.TRANSFER_ASSET_INIT,
#         initiator_id=initiator_id,
#         status=NotificationStatus.UNREAD,
#         assignment_type=request.assignment_type
#     )
#     db.add(notification)
#     await db.commit()
#     await db.refresh(notification)
#
#     # 5. Формируем подробный ответ
#     assignment_type_ru = "Пользователь" if request.assignment_type == "user" else "Ответственный"
#
#     return AssetTransferResponse(
#         message="Запрос на передачу актива успешно создан",
#         action="transfer_initiated",
#         notification=NotificationInfoResponse(
#             notification_id=notification.notification_id,
#             event_type=notification.event_type,
#             event_type_ru="Инициация передачи актива",
#             status=notification.status,
#             created_at=notification.created_at
#         ),
#         asset=AssetInfoResponse(
#             asset_id=asset.asset_id,
#             inventory_id=asset.inventory_id,
#             name=asset.name,
#             serial_number=asset.serial_number,
#             asset_type_id=asset.asset_type_id,
#             model_id=asset.model_id,
#             source=asset_source
#         ),
#         initiator=EmployeeInfoResponse(
#             employee_id=initiator_id,
#             full_name=initiator_name
#         ),
#         target_employee=EmployeeInfoResponse(
#             employee_id=request.target_employee_id,
#             full_name=target_name
#         ),
#         assignment_type=request.assignment_type,
#         assignment_type_ru=assignment_type_ru,
#         comment=request.comment,
#         created_at=notification.created_at
#     )
#
# async def respond_to_asset_transfer(
#         db: AsyncSession,
#         notification_id: int,
#         action: str,
#         responder_id: str,
#         comment: Optional[str] = None
# ) -> AssetTransferRespondResponse:
#     """
#     Обработать ответ на запрос передачи и вернуть подробный ответ
#     """
#     result = await db.execute(
#         select(Notification).where(Notification.notification_id == notification_id)
#     )
#     notification = result.scalar_one_or_none()
#
#     if not notification:
#         raise ValueError("Уведомление не найдено")
#     if notification.employee_id != responder_id:
#         raise ValueError("Вы не являетесь получателем этого уведомления")
#     if notification.status != NotificationStatus.UNREAD:
#         raise ValueError("На это уведомление уже был дан ответ")
#
#     asset_id = notification.asset_id
#     initiator_id = notification.initiator_id
#     assignment_type = notification.assignment_type or "user"
#
#     # Получаем информацию об активе
#     asset_result = await db.execute(select(Asset).where(Asset.asset_id == asset_id))
#     asset = asset_result.scalar_one()
#
#     # Получаем имена участников
#     initiator_name = await get_employee_full_name(db, initiator_id)
#     responder_name = await get_employee_full_name(db, responder_id)
#
#     # Помечаем текущее уведомление как обработанное
#     notification.status = NotificationStatus.READ
#     notification.responded_at = datetime.utcnow()
#
#     assignment_type_ru = "Пользователь" if assignment_type == "user" else "Ответственный"
#     new_assignment_id = None
#     previous_assignment_closed = False
#
#     if action == "decline":
#         # Уведомляем инициатора об отказе
#         decline_notification = Notification(
#             employee_id=initiator_id,
#             asset_id=asset_id,
#             event_type=NotificationEventType.TRANSFER_ASSET_DECLINED,
#             initiator_id=responder_id,
#             status=NotificationStatus.UNREAD,
#             assignment_type=assignment_type
#         )
#         db.add(decline_notification)
#         response_msg = "Передача актива отклонена"
#         response_notification = decline_notification
#
#     elif action == "accept":
#         # Отвязываем текущий актив (если есть активная привязка данного типа)
#         active_assignment_result = await db.execute(
#             select(AssetAssignment).where(
#                 AssetAssignment.asset_id == asset_id,
#                 AssetAssignment.assignment_type == assignment_type,
#                 AssetAssignment.end_date.is_(None)
#             )
#         )
#         active_assignment = active_assignment_result.scalar_one_or_none()
#
#         if active_assignment:
#             active_assignment.end_date = date.today()
#             previous_assignment_closed = True
#
#         # Создаем новую привязку для получателя
#         new_assignment = AssetAssignment(
#             asset_id=asset_id,
#             employee_id=responder_id,
#             assignment_type=assignment_type,
#             start_date=date.today(),
#             end_date=None,
#             assigned_by=initiator_id,
#             comment=comment
#         )
#         db.add(new_assignment)
#
#         # Уведомляем инициатора об успехе
#         accept_notification = Notification(
#             employee_id=initiator_id,
#             asset_id=asset_id,
#             event_type=NotificationEventType.TRANSFER_ASSET_ACCEPTED,
#             initiator_id=responder_id,
#             status=NotificationStatus.UNREAD,
#             assignment_type=assignment_type
#         )
#         db.add(accept_notification)
#         response_msg = "Передача актива успешно завершена"
#         response_notification = accept_notification
#
#     else:
#         raise ValueError("Недопустимое действие")
#
#     await db.commit()
#     await db.refresh(response_notification)
#
#     # Получаем ID новой привязки если было принятие
#     if action == "accept":
#         new_assignment_result = await db.execute(
#             select(AssetAssignment).where(
#                 AssetAssignment.asset_id == asset_id,
#                 AssetAssignment.employee_id == responder_id,
#                 AssetAssignment.assignment_type == assignment_type,
#                 AssetAssignment.end_date.is_(None)
#             ).order_by(AssetAssignment.id.desc())
#         )
#         new_assignment_obj = new_assignment_result.scalars().first()
#         if new_assignment_obj:
#             new_assignment_id = new_assignment_obj.id
#
#     # Формируем подробный ответ
#     event_type_ru_map = {
#         NotificationEventType.TRANSFER_ASSET_DECLINED: "Передача актива отклонена",
#         NotificationEventType.TRANSFER_ASSET_ACCEPTED: "Передача актива принята"
#     }
#
#     return AssetTransferRespondResponse(
#         message=response_msg,
#         action=action,
#         notification=NotificationInfoResponse(
#             notification_id=response_notification.notification_id,
#             event_type=response_notification.event_type,
#             event_type_ru=event_type_ru_map.get(response_notification.event_type, "Ответ на передачу"),
#             status=response_notification.status,
#             created_at=response_notification.created_at
#         ),
#         asset=AssetInfoResponse(
#             asset_id=asset.asset_id,
#             inventory_id=asset.inventory_id,
#             name=asset.name,
#             serial_number=asset.serial_number,
#             asset_type_id=asset.asset_type_id,
#             model_id=asset.model_id,
#             source="local"  # К этому моменту актив всегда локальный
#         ),
#         initiator=EmployeeInfoResponse(
#             employee_id=initiator_id,
#             full_name=initiator_name
#         ),
#         responder=EmployeeInfoResponse(
#             employee_id=responder_id,
#             full_name=responder_name
#         ),
#         assignment_type=assignment_type,
#         assignment_type_ru=assignment_type_ru,
#         comment=comment,
#         responded_at=notification.responded_at,
#         new_assignment_id=new_assignment_id,
#         previous_assignment_closed=previous_assignment_closed
#     )


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

async def get_employee_full_name(db: AsyncSession, employee_id: str) -> Optional[str]:
    result = await db.execute(select(Employee).where(Employee.employee_id == employee_id))
    employee = result.scalar_one_or_none()
    if not employee:
        return None
    parts = [p for p in [employee.last_name, employee.first_name, employee.middle_name] if p]
    return " ".join(parts) if parts else None

async def fetch_sap_asset_data(material_id: str) -> Dict[str, Any]:
    """
    ЗАГЛУШКА: Получение данных об активе из SAP по material_id.
    TODO: Замените этот код на реальный асинхронный запрос к вашему SAP API через httpx.
    """
    # Пример реального запроса:
    # async with httpx.AsyncClient() as client:
    #     response = await client.get(f"http://10.168.143.7:8123/sap/materials/{material_id}")
    #     return response.json()

    # Возвращаем моковые данные, которые гарантированно содержат все нужные поля
    return {
        "inventory_id": material_id,
        "name": f"Актив SAP (Material: {material_id})",
        "asset_type_id": 10,  # Замените на реальную логику маппинга типов из SAP
        "asset_status_id": 9, # "На складе"
        "quantity": 1,
        "every_week_check": False, # ВАЖНО: Явное указание boolean предотвращает ошибку SQLAlchemy!
        "model_id": None,
        "serial_number": None
    }

async def create_asset_from_sap_material(db: AsyncSession, sap_material_id: str, created_by: str) -> Asset:
    sap_data = await fetch_sap_asset_data(sap_material_id)

    new_asset = Asset(
        material_id=sap_material_id,          # Сохраняем исходный ID материала
        inventory_id=sap_data.get("inventory_id", sap_material_id),
        name=sap_data["name"],
        serial_number=sap_data.get("serial_number"),
        asset_type_id=sap_data["asset_type_id"],
        model_id=sap_data.get("model_id"),
        asset_status_id=sap_data["asset_status_id"],
        quantity=sap_data.get("quantity", 1),
        every_week_check=sap_data.get("every_week_check", False), # Явно задаем boolean!
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
) -> AssetTransferResponse:
    asset_id = request.asset_id
    asset_source = "local"

    if request.sap_material_id:
        try:
            new_asset = await create_asset_from_sap_material(db, request.sap_material_id, initiator_id)
            asset_id = new_asset.asset_id
            asset_source = "sap"
        except IntegrityError:
            await db.rollback()
            raise ValueError(f"Актив с material_id/inventory_id {request.sap_material_id} уже существует локально")

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

# ... (функция respond_to_asset_transfer остается без изменений, она уже правильная) ...
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