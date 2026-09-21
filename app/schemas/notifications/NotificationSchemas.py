# import logging
# from pydantic import BaseModel, ConfigDict, computed_field, Field, model_validator, ValidationInfo
# from datetime import datetime
# from typing import Optional, List
#
# from app.models.notifications.Notification import NotificationEventType
#
# logger = logging.getLogger(__name__)
#
# class NotificationBase(BaseModel):
#     employee_id: str
#     asset_id: Optional[int] = None
#     session_id: Optional[int] = None
#     event_type: str
#     event_type_ru: Optional[str] = None
#     initiator_id: Optional[str] = None
#     status: str = "unread"
#     status_ru: Optional[str] = None
#
#
# class NotificationResponse(BaseModel):
#     notification_id: int
#     employee_id: str
#     employee_full_name: Optional[str] = None
#     asset_id: Optional[int] = None
#     session_id: Optional[int] = None
#     event_type: str
#     initiator_id: Optional[str] = None
#     status: str
#     responded_at: Optional[datetime] = None
#     created_at: datetime
#     asset_name: Optional[str] = None
#     asset_inventory_id: Optional[str] = None
#     initiator_full_name: Optional[str] = None
#
#     # exclude=True важен: поле нужно для логики, но не должно уходить в JSON фронтенду
#     viewer_id: Optional[str] = Field(default=None, exclude=True)
#     direction: Optional[str] = None
#     direction_ru: Optional[str] = None
#
#     model_config = ConfigDict(from_attributes=True)
#
#     @model_validator(mode='after')
#     def inject_viewer_id_from_context(self, info: ValidationInfo):
#         """Забирает viewer_id из контекста, нормализуя его"""
#         if info.context and "viewer_id" in info.context:
#             # Приводим к строке и убираем все скрытые пробелы по краям
#             self.viewer_id = str(info.context["viewer_id"]).strip()
#         return self
#
#     @model_validator(mode='after')
#     def inject_direction_from_context(self, info: ValidationInfo):
#         viewer = str(self.viewer_id).strip() if self.viewer_id else ""
#         initiator = str(self.initiator_id).strip() if self.initiator_id else ""
#         recipient = str(self.employee_id).strip() if self.employee_id else ""
#
#         is_initiator = (initiator == viewer and viewer != "")
#         is_recipient = (recipient == viewer and viewer != "")
#
#         if info.context and "direction" in info.context:
#             raw_direction = str(info.context["direction"]).strip()
#             self.direction = raw_direction
#
#             if is_initiator and not is_recipient:
#                 self.direction = "outgoing"
#                 self.direction_ru = "Исходящее"
#             else:
#                 self.direction = "incoming"
#                 self.direction_ru = "Входящее"
#         return self
#
#     @computed_field
#     @property
#     def event_type_ru(self) -> str:
#         """Единая логика формирования текста строго по роли зрителя"""
#         # 100% надежное сравнение: приводим к строке и убираем пробелы
#         viewer = str(self.viewer_id).strip() if self.viewer_id else ""
#         initiator = str(self.initiator_id).strip() if self.initiator_id else ""
#         recipient = str(self.employee_id).strip() if self.employee_id else ""
#
#         is_initiator = (initiator == viewer and viewer != "")
#         is_recipient = (recipient == viewer and viewer != "")
#
#         # === ВРЕМЕННЫЙ ОТЛАДОЧНЫЙ ЛОГ ===
#         # Посмотрите в консоль сервера после запроса. Вы увидите точные значения в кавычках.
#         # Если есть пробел, вы его сразу заметите, например: initiator='0000015370 '
#         logger.warning(
#             f"DEBUG event_type_ru: viewer='{viewer}', initiator='{initiator}', "
#             f"recipient='{recipient}', is_init={is_initiator}, is_rec={is_recipient}, "
#             f"event='{self.event_type}'"
#         )
#         # ================================
#
#         messages = {
#             NotificationEventType.SERVICE_DUE: ("Требуется обслуживание актива", "Требуется обслуживание актива"),
#             NotificationEventType.ASSET_STATUS_CHANGED: ("Изменение статуса актива", "Изменение статуса актива"),
#             NotificationEventType.ASSIGNED_RESPONSIBLE: ("Вы назначили сотрудника ответственным за актив", "Вас назначили ответственным за актив"),
#             NotificationEventType.ASSIGNED_USER: ("Вы назначили сотрудника пользователем актива", "Вас назначили пользователем актива"),
#             NotificationEventType.UNASSIGNED_RESPONSIBLE: ("Вы открепили сотрудника от ответственности", "Вас открепили как ответственного за актив"),
#             NotificationEventType.UNASSIGNED_USER: ("Вы открепили сотрудника от актива", "Вас открепили как пользователя активом"),
#             NotificationEventType.RESPONSIBLE_DECLINED: ("Сотрудник отклонил ваше назначение ответственным", "Вы отклонили назначение ответственным"),
#             NotificationEventType.USER_DECLINED: ("Сотрудник отклонил ваше назначение пользователем", "Вы отклонили назначение пользователем"),
#             NotificationEventType.ASSIGNED_SERVING: ("Вы назначали сотрудника обслуживать актив", "Вас назначили обслуживать актив"),
#             NotificationEventType.UNASSIGNED_SERVING: ("Вы открепили сотрудника обслуживающего актив", "Вас открепили обслуживать актив"),
#             NotificationEventType.WRITE_OFF_REQUESTED: ("Вы создали заявку на списание", "Создана заявка на списание актива"),
#             NotificationEventType.WRITE_OFF_APPROVED: ("Вы утвердили заявку на списание", "Ваша заявка на списание утверждена"),
#             NotificationEventType.WRITE_OFF_REJECTED: ("Вы отклонили заявку на списание", "Ваша заявка на списание отклонена"),
#             NotificationEventType.INVENTORY_STARTED: ("Вы запустили новую сессию инвентаризации", "Началась инвентаризация закрепленных за вами активов"),
#             NotificationEventType.INVENTORY_DISCREPANCY: ("Вы зафиксировали расхождение при инвентаризации", "Обнаружено расхождение по закрепленному за вами активу при инвентаризации"),
#             NotificationEventType.INVENTORY_COMPLETED: ("Вы завершили сессию инвентаризации", "Сессия инвентаризации, затрагивающая ваши активы, завершена"),
#             NotificationEventType.TRANSFER_ASSET_INIT: ("Вы инициировали передачу актива", "Вам принять актив"),
#             NotificationEventType.TRANSFER_ASSET_DECLINED: ("Получатель отклонил передачу актива", "Вы отклонили передачу актива"),
#             NotificationEventType.TRANSFER_ASSET_ACCEPTED: ("Получатель принял передачу актива", "Вы приняли передачу актива"),
#         }
#
#         # type_messages = messages.get(self.event_type, ("Уведомление", "Уведомление"))
#         #
#         # if is_initiator and not is_recipient:
#         #     return type_messages[0]
#         #
#         # return type_messages[1]
#         # type_messages = ('Уведомление', 'Уведомление')
#         type_messages = "EMPTY"
#         if initiator == viewer:
#             type_messages = messages.get(self.event_type[0], ('Уведомление', 'Уведомление'))
#             return type_messages
#         if recipient == viewer:
#             type_messages = messages.get(self.event_type[1], ('Уведомление', 'Уведомление'))
#             return type_messages
#         return type_messages
#
#     @computed_field
#     @property
#     def status_ru(self) -> str:
#         statuses = {"unread": "Не прочитано", "read": "Прочитано"}
#         return statuses.get(self.status, self.status)
#
#
# class PaginatedNotificationResponse(BaseModel):
#     items: List[NotificationResponse]
#     total: int
#     page: int
#     page_size: int
#     total_pages: int
#     has_next: bool
#     has_previous: bool
#     unchecked_count: int
#     checked_count: int
#
#
# class NotificationGroupedItem(BaseModel):
#     asset_id: Optional[int] = None
#     session_id: Optional[int] = None
#     asset_name: Optional[str] = None
#     asset_inventory_id: Optional[str] = None
#     notifications: List[NotificationResponse]
#     total: int
#     unread_count: int

import logging
from pydantic import BaseModel, ConfigDict, Field, model_validator, ValidationInfo
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

    # Поля для логики и отображения (теперь обычные поля, а не @computed_field)
    viewer_id: Optional[str] = Field(default=None, exclude=True)
    direction: Optional[str] = None
    direction_ru: Optional[str] = None
    event_type_ru: Optional[str] = None
    status_ru: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode='after')
    def compute_display_fields(self, info: ValidationInfo):
        """
        Вычисляет все зависимые поля один раз и сохраняет их в модель.
        Это решает проблему потери контекста при повторной валидации FastAPI.
        """
        # 1. Определяем viewer_id (из контекста или из уже сохраненного значения при повторной валидации)
        viewer = ""
        if info.context and "viewer_id" in info.context:
            viewer = str(info.context["viewer_id"]).strip()
        elif self.viewer_id:
            viewer = str(self.viewer_id).strip()

        self.viewer_id = viewer # Сохраняем, чтобы не потерять при повторной валидации FastAPI

        initiator = str(self.initiator_id).strip() if self.initiator_id else ""
        recipient = str(self.employee_id).strip() if self.employee_id else ""

        is_initiator = (initiator == viewer and viewer != "")
        is_recipient = (recipient == viewer and viewer != "")

        # 2. Вычисляем direction
        if info.context and "direction" in info.context:
            if is_initiator and not is_recipient:
                self.direction = "outgoing"
                self.direction_ru = "Исходящее"
            else:
                raw_direction = str(info.context["direction"]).strip()
                self.direction = raw_direction
                self.direction_ru = "Входящее"

        # 3. Вычисляем event_type_ru (один раз и сохраняем в поле)
        messages = {
            NotificationEventType.SERVICE_DUE: ("Требуется обслуживание актива", "Требуется обслуживание актива"),
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
            NotificationEventType.TRANSFER_ASSET_DECLINED: ("Получатель отклонил передачу актива", "Вы отклонили передачу актива"),
            NotificationEventType.TRANSFER_ASSET_ACCEPTED: ("Получатель принял передачу актива", "Вы приняли передачу актива"),
        }

        type_messages = messages.get(self.event_type, ("Уведомление", "Уведомление"))
        if is_initiator and not is_recipient:
            self.event_type_ru = type_messages[0]
        else:
            self.event_type_ru = type_messages[1]

        # 4. Вычисляем status_ru
        statuses = {"unread": "Не прочитано", "read": "Прочитано"}
        self.status_ru = statuses.get(self.status, self.status)

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