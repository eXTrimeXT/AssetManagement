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


# class NotificationResponse(NotificationBase):
#     notification_id: int
#     responded_at: Optional[datetime] = None
#     created_at: datetime
#
#     # Данные об активе
#     asset_name: Optional[str] = None
#     asset_inventory_id: Optional[str] = None
#
#     # Данные об инициаторе
#     initiator_full_name: Optional[str] = None
#
#     model_config = ConfigDict(from_attributes=True)


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

    # Связанные данные (из model)
    asset_name: Optional[str] = None
    asset_inventory_id: Optional[str] = None
    initiator_full_name: Optional[str] = None

    # Поле для внутреннего использования, чтобы знать, для кого генерируем текст
    viewer_id: Optional[str] = Field(default=None, exclude=True)

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def event_type_ru(self) -> str:
        """Динамическое формирование текста в зависимости от роли зрителя"""
        is_recipient = (self.employee_id == self.viewer_id)     # Получатель
        is_initiator = (self.initiator_id == self.viewer_id)    # Инициатор

        # Словарь сообщений: ключ - event_type, значение - кортеж (сообщение_для_получателя, сообщение_для_инициатора)
        messages = {
            "assigned_responsible": (
                "Вы назначены ответственным за актив",
                "Вы назначили сотрудника ответственным за актив"
            ),
            "assigned_user": (
                "Вы назначены пользователем актива",
                "Вы назначили сотрудника пользователем актива"
            ),
            "unassigned_responsible": (
                "Вы откреплены как ответственный",
                "Вы открепили сотрудника от ответственности"
            ),
            "unassigned_user": (
                "Вы откреплены как пользователь",
                "Вы открепили сотрудника от актива"
            ),
            "write_off_requested": (
                "Создана заявка на списание актива",
                "Вы создали заявку на списание актива"
            ),
            "write_off_approved": (
                "Заявка на списание утверждена",
                "Вы утвердили заявку на списание"
            ),
            "write_off_rejected": (
                "Заявка на списание отклонена",
                "Вы отклонили заявку на списание"
            ),
            "responsible_declined": (
                "Сотрудник отклонил назначение ответственным",
                "Сотрудник отклонил ваше назначение ответственным"
            ),
            "user_declined": (
                "Сотрудник отклонил назначение пользователем",
                "Сотрудник отклонил ваше назначение пользователем"
            ),
        }

        type_messages = messages.get(self.event_type, ("Исходящее (наше)", "входящее (нам)"))
        # Всегда делаем проверку на исходящее уведомление, потому что входящее легче проверить
        if is_initiator and not is_recipient:
            return type_messages[0]
        elif not is_initiator and is_recipient:
            return type_messages[1]
        return "Что-то пошло не так!"

    @computed_field
    @property
    def status_ru(self) -> str:
        statuses = {
            "unread": "Не прочитано",
            "read": "Прочитано",
            "declined": "Отклонено"
        }
        return statuses.get(self.status, self.status)


class PaginatedNotificationResponse(BaseModel):
    """Ответ со списком уведомлений и количеством непрочитанных"""
    items: List[NotificationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool
    unchecked_count: int
    checked_count: int
    declined_count: int


class NotificationGroupedItem(BaseModel):
    """Группа уведомлений по активу"""
    asset_id: int
    asset_name: Optional[str] = None
    asset_inventory_id: Optional[str] = None
    notifications: List[NotificationResponse]
    total: int
    unread_count: int


class NotificationDeclineResponse(BaseModel):
    message: str
    notification_id: int