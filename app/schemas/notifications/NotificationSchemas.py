import logging
from pydantic import BaseModel, ConfigDict, computed_field, Field, model_validator, ValidationInfo
from datetime import datetime
from typing import Optional, List

from app.models.notifications.Notification import NotificationEventType

logger = logging.getLogger(__name__)

class NotificationBase(BaseModel):
    employee_id: str
    asset_id: Optional[int] = None
    session_id: Optional[int] = None
    event_type: str
    event_type_ru: Optional[str] = None
    initiator_id: Optional[str] = None
    status: str = "unread"
    status_ru: Optional[str] = None

class NotificationResponse(BaseModel):
    notification_id: int
    employee_id: str
    employee_full_name: Optional[str] = None
    asset_id: Optional[int] = None
    session_id: Optional[int] = None
    event_type: str
    initiator_id: Optional[str] = None
    status: str
    responded_at: Optional[datetime] = None
    created_at: datetime
    asset_name: Optional[str] = None
    asset_inventory_id: Optional[str] = None
    initiator_full_name: Optional[str] = None

    viewer_id: Optional[str] = Field(default=None, exclude=True)

    direction: Optional[str] = None
    direction_ru: Optional[str] = None
    event_type_ru: Optional[str] = None
    status_ru: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode='after')
    def fill_derived(self, info: ValidationInfo):
        if info.context and "viewer_id" in info.context:
            self.viewer_id = str(info.context["viewer_id"]).strip()

        viewer = (self.viewer_id or "").strip()
        initiator = (self.initiator_id or "").strip()
        recipient = (self.employee_id or "").strip()

        is_initiator = bool(viewer) and initiator == viewer
        is_recipient = bool(viewer) and recipient == viewer

        messages = {
            NotificationEventType.SERVICE_REQUIRE: ("Требуется обслуживание актива", "Требуется обслуживание актива"),
            NotificationEventType.CHECK_REQUIRE: ("Требуется проверить актив", "Требуется проверить актив"),
            NotificationEventType.ASSET_STATUS_CHANGED: ("Изменение статуса актива", "Изменение статуса актива"),
            NotificationEventType.ASSIGNED_RESPONSIBLE: ("Вы назначили сотрудника ответственным за актив", "Вас назначили ответственным за актив"),
            NotificationEventType.ASSIGNED_USER: ("Вы назначили сотрудника пользователем актива", "Вас назначили пользователем актива"),
            NotificationEventType.UNASSIGNED_RESPONSIBLE: ("Вы открепили сотрудника от ответственности", "Вас открепили как ответственного за актив"),
            NotificationEventType.UNASSIGNED_USER: ("Вы открепили сотрудника от актива", "Вас открепили как пользователя активом"),
            NotificationEventType.RESPONSIBLE_DECLINED: ("Сотрудник отклонил ваше назначение ответственным", "Вы отклонили назначение ответственным"),
            NotificationEventType.USER_DECLINED: ("Сотрудник отклонил ваше назначение пользователем", "Вы отклонили назначение пользователем"),
            NotificationEventType.ASSIGNED_SERVING: ("Вы назначали сотрудника обслуживать актив", "Вас назначили обслуживать актив"),
            NotificationEventType.UNASSIGNED_SERVING: ("Вы открепили сотрудника обслуживающего актив", "Вас открепили обслуживать актив"),
            NotificationEventType.WRITE_OFF_REQUESTED: ("Вы создали заявку на списание", "Создана заявка на списание актива"),
            NotificationEventType.WRITE_OFF_APPROVED: ("Вы утвердили заявку на списание", "Ваша заявка на списание утверждена"),
            NotificationEventType.WRITE_OFF_REJECTED: ("Вы отклонили заявку на списание", "Ваша заявка на списание отклонена"),
            NotificationEventType.INVENTORY_STARTED: ("Вы запустили новую сессию инвентаризации", "Началась инвентаризация закрепленных за вами активов"),
            NotificationEventType.INVENTORY_DISCREPANCY: ("Вы зафиксировали расхождение при инвентаризации", "Обнаружено расхождение по закрепленному за вами активу при инвентаризации"),
            NotificationEventType.INVENTORY_COMPLETED: ("Вы завершили сессию инвентаризации", "Сессия инвентаризации, затрагивающая ваши активы, завершена"),
            NotificationEventType.TRANSFER_ASSET_INIT: ("Вы инициировали передачу актива", "Вам предложено принять актив"),
            NotificationEventType.TRANSFER_ASSET_DECLINED: ("Вы отклонили передачу актива", "Получатель отклонил передачу актива"),
            NotificationEventType.TRANSFER_ASSET_ACCEPTED: ("Вы приняли передачу актива", "Получатель принял передачу актива"),
        }

        pair = messages.get(self.event_type, ("Уведомление", "Уведомление"))
        self.event_type_ru = pair[0] if (is_initiator and not is_recipient) else pair[1]

        self.status_ru = {"unread": "Не прочитано", "read": "Прочитано"}.get(self.status, self.status)

        if info.context and "direction" in info.context:
            self.direction = str(info.context["direction"]).strip()
        else:
            self.direction = "outgoing" if (is_initiator and not is_recipient) else "incoming"
        self.direction_ru = "Исходящее" if self.direction == "outgoing" else "Входящее"

        return self

class PaginatedNotificationResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool
    unchecked_count: int
    checked_count: int


class NotificationGroupedItem(BaseModel):
    asset_id: Optional[int] = None
    session_id: Optional[int] = None
    asset_name: Optional[str] = None
    asset_inventory_id: Optional[str] = None
    notifications: List[NotificationResponse]
    total: int
    unread_count: int