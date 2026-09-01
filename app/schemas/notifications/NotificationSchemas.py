from pydantic import BaseModel, ConfigDict, computed_field, Field, model_validator, ValidationInfo
from datetime import datetime
from typing import Optional, List

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

    # exclude=True важен: поле нужно для логики, но не должно уходить в JSON фронтенду
    viewer_id: Optional[str] = Field(default=None, exclude=True)

    direction: Optional[str] = None
    direction_ru: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode='after')
    def inject_viewer_id_from_context(self, info: ValidationInfo):
        """Забирает viewer_id из контекста валидации, если он был передан"""
        if info.context and "viewer_id" in info.context:
            self.viewer_id = info.context["viewer_id"]
        return self

    @computed_field
    @property
    def event_type_ru(self) -> str:
        """Единая логика формирования текста строго по роли зрителя"""
        is_initiator = (self.initiator_id == self.viewer_id)
        is_recipient = (self.employee_id == self.viewer_id)

        # Единый словарь сообщений: (текст_для_инициатора (исходящее), текст_для_получателя (входящее))
        messages = {
            "service_due": ("Требуется обслуживание актива", "Требуется обслуживание актива"),

            "assigned_responsible": ("Вы назначили сотрудника ответственным за актив", "Вы назначены ответственным за актив"),
            "assigned_user": ("Вы назначили сотрудника пользователем актива", "Вы назначены пользователем актива"),
            "unassigned_responsible": ("Вы открепили сотрудника от ответственности", "Вы откреплены как ответственный"),
            "unassigned_user": ("Вы открепили сотрудника от актива", "Вы откреплены как пользователь"),
            "responsible_declined": ("Сотрудник отклонил ваше назначение ответственным", "Вы отклонили назначение ответственным"),
            "user_declined": ("Сотрудник отклонил ваше назначение пользователем", "Вы отклонили назначение пользователем"),

            "write_off_requested": ("Вы создали заявку на списание", "Создана заявка на списание актива"),
            "write_off_approved": ("Вы утвердили заявку на списание", "Ваша заявка на списание утверждена"),
            "write_off_rejected": ("Вы отклонили заявку на списание", "Ваша заявка на списание отклонена"),

            "inventory_started": ("Вы запустили новую сессию инвентаризации", "Началась инвентаризация закрепленных за вами активов"),
            "inventory_discrepancy": ("Вы зафиксировали расхождение при инвентаризации", "Обнаружено расхождение по закрепленному за вами активу при инвентаризации"),
            "inventory_completed": ("Вы завершили сессию инвентаризации", "Сессия инвентаризации, затрагивающая ваши активы, завершена"),
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
        statuses = {"unread": "Не прочитано", "read": "Прочитано"}
        return statuses.get(self.status, self.status)


    @model_validator(mode='after')
    def inject_direction_from_context(self, info: ValidationInfo):
        is_initiator = (self.initiator_id == self.viewer_id)
        is_recipient = (self.employee_id == self.viewer_id)

        if info.context and "direction" in info.context:
            self.direction = info.context["direction"]
            if is_initiator and not is_recipient:
                self.direction = "outgoing"
                self.direction_ru = "Исходящее"
            else:
                self.direction = "incoming"
                self.direction_ru = "Входящее"
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
