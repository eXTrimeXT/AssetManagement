from pydantic import BaseModel, ConfigDict, computed_field, Field
from datetime import datetime
from typing import Optional, List

class NotificationBase(BaseModel):
    employee_id: str
    asset_id: int
    event_type: str
    event_type_ru: Optional[str] = None
    initiator_id: Optional[str] = None
    status: str = "unread"
    status_ru: Optional[str] = None

class NotificationResponse(BaseModel):
    notification_id: int
    employee_id: str
    employee_full_name: Optional[str] = None
    asset_id: int
    event_type: str
    initiator_id: Optional[str] = None
    status: str
    responded_at: Optional[datetime] = None
    created_at: datetime

    asset_name: Optional[str] = None
    asset_inventory_id: Optional[str] = None
    initiator_full_name: Optional[str] = None

    # Поле для внутреннего использования (не попадет в JSON)
    viewer_id: Optional[str] = Field(default=None, exclude=True)

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def event_type_ru(self) -> str:
        """Формирование текста строго по роли зрителя"""
        is_initiator = (self.initiator_id == self.viewer_id)
        is_recipient = (self.employee_id == self.viewer_id)

        # Кортеж: (текст_для_инициатора, текст_для_получателя)
        messages = {
            "assigned_responsible": ("Вы назначили сотрудника ответственным за актив", "Вы назначены ответственным за актив"),
            "assigned_user": ("Вы назначили сотрудника пользователем актива", "Вы назначены пользователем актива"),
            "unassigned_responsible": ("Вы открепили сотрудника от ответственности", "Вы откреплены как ответственный"),
            "unassigned_user": ("Вы открепили сотрудника от актива", "Вы откреплены как пользователь"),
            "write_off_requested": ("Вы создали заявку на списание", "Создана заявка на списание актива"),
            "write_off_approved": ("Вы утвердили заявку на списание", "Ваша заявка на списание утверждена"),
            "write_off_rejected": ("Вы отклонили заявку на списание", "Ваша заявка на списание отклонена"),
            "responsible_declined": ("Сотрудник отклонил ваше назначение ответственным", "Вы отклонили назначение ответственным"),
            "user_declined": ("Сотрудник отклонил ваше назначение пользователем", "Вы отклонили назначение пользователем"),
            "service_due": ("Требуется обслуживание актива", "Требуется обслуживание актива"),
        }

        type_messages = messages.get(self.event_type, ("Уведомление", "Уведомление"))

        # Если зритель является инициатором (и не является получателем одновременно)
        if is_initiator and not is_recipient:
            return type_messages[0]

        # Во всех остальных случаях (зритель - получатель, или системное уведомление без инициатора)
        return type_messages[1]

    @computed_field
    @property
    def status_ru(self) -> str:
        statuses = {"unread": "Не прочитано", "read": "Прочитано", "declined": "Отклонено"}
        return statuses.get(self.status, self.status)


class PaginatedNotificationResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool
    unchecked_count: int
    checked_count: int      # НОВОЕ
    declined_count: int     # НОВОЕ


class NotificationGroupedItem(BaseModel):
    asset_id: int
    asset_name: Optional[str] = None
    asset_inventory_id: Optional[str] = None
    notifications: List[NotificationResponse]
    total: int
    unread_count: int


class NotificationDeclineResponse(BaseModel):
    message: str
    notification_id: int