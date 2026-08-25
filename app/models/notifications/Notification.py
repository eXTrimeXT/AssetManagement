from datetime import datetime
from typing import Optional
from pydantic import computed_field

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.Base import Base


class NotificationEventType:
    """Типы событий уведомлений"""
    SERVICE_DUE = "service_due"
    ASSIGNED_RESPONSIBLE = "assigned_responsible"
    RESPONSIBLE_DECLINED = "responsible_declined"
    ASSIGNED_USER = "assigned_user"
    USER_DECLINED = "user_declined"
    UNASSIGNED_RESPONSIBLE = "unassigned_responsible"
    UNASSIGNED_USER = "unassigned_user"

    # === события списания ===
    WRITE_OFF_REQUESTED = "write_off_requested"
    WRITE_OFF_APPROVED = "write_off_approved"
    WRITE_OFF_REJECTED = "write_off_rejected"

    # === РУССКИЕ НАЗВАНИЯ ===
    RU_LABELS = {
        SERVICE_DUE: "Требуется обслуживание",
        ASSIGNED_RESPONSIBLE: "Вы назначены ответственным за актив",
        RESPONSIBLE_DECLINED: "Ответственный отклонил назначение",
        ASSIGNED_USER: "Вы назначены пользователем актива",
        USER_DECLINED: "Пользователь отклонил назначение",
        UNASSIGNED_RESPONSIBLE: "Вы откреплены как ответственный",
        UNASSIGNED_USER: "Вы откреплены как пользователь",
        WRITE_OFF_REQUESTED: "Создана заявка на списание",
        WRITE_OFF_APPROVED: "Заявка на списание утверждена",
        WRITE_OFF_REJECTED: "Заявка на списание отклонена",
    }

    @classmethod
    def get_ru_label(cls, event_type: str) -> str:
        """Получить русское название типа события"""
        return cls.RU_LABELS.get(event_type, event_type)


class NotificationStatus:
    """Статусы уведомлений"""
    UNREAD = "unread"
    READ = "read"
    DECLINED = "declined"

    # === РУССКИЕ НАЗВАНИЯ ===
    RU_LABELS = {
        UNREAD: "Не прочитано",
        READ: "Прочитано",
        DECLINED: "Отклонено",
    }

    @classmethod
    def get_ru_label(cls, status: str) -> str:
        """Получить русское название статуса"""
        return cls.RU_LABELS.get(status, status)


class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    employee_id = Column(String(20), ForeignKey("zup_employees.employee_id"), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    initiator_id = Column(String(20), ForeignKey("zup_employees.employee_id"), nullable=True)
    status = Column(String(20), nullable=False, default=NotificationStatus.UNREAD, index=True)
    responded_at = Column(DateTime(), nullable=True)
    created_at = Column(DateTime(), default=datetime.now)

    # Relationships
    asset = relationship("Asset", foreign_keys=[asset_id], lazy="selectin")
    initiator = relationship("Employee", foreign_keys=[initiator_id])
    recipient = relationship("Employee", foreign_keys=[employee_id])

    # === РУССКИЕ НАЗВАНИЯ (вычисляемые поля) ===
    @computed_field
    @property
    def event_type_ru(self) -> Optional[str]:
        """Тип события на русском"""
        if not self.event_type:
            return None
        return NotificationEventType.get_ru_label(self.event_type)

    @computed_field
    @property
    def status_ru(self) -> Optional[str]:
        """Статус на русском"""
        if not self.status:
            return None
        return NotificationStatus.get_ru_label(self.status)

    def __repr__(self):
        return f"<Notification(id={self.notification_id}, type={self.event_type}, status={self.status})>"