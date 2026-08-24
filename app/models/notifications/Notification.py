from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
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
    WRITE_OFF_REQUESTED = "write_off_requested"  # Заявка создана → ответственным
    WRITE_OFF_APPROVED = "write_off_approved"    # Заявка утверждена → инициатору
    WRITE_OFF_REJECTED = "write_off_rejected"    # Заявка отклонена → инициатору

class NotificationStatus:
    """Статусы уведомлений"""
    UNREAD = "unread"
    READ = "read"
    DECLINED = "declined"


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

    def __repr__(self):
        return f"<Notification(id={self.notification_id}, type={self.event_type}, status={self.status})>"