from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from app.models.Base import Base


class WriteOffStatus:
    """Статусы заявки на списание"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class WriteOffType:
    """Типы списания"""
    BROKEN = "broken"      # Сломан
    LOST = "lost"          # Утерян
    OBSOLETE = "obsolete"  # Устарел
    SOLD = "sold"          # Продан
    OTHER = "other"        # Другое


class AssetWriteOff(Base):
    __tablename__ = "asset_write_offs"

    write_off_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False, index=True)

    # Информация о списании
    reason = Column(Text, nullable=False)
    write_off_type = Column(String(50), nullable=False, default=WriteOffType.OTHER)

    # Процесс утверждения
    requested_by = Column(String(20), ForeignKey("zup_employees.employee_id"), nullable=False)
    requested_at = Column(DateTime(),  default=datetime.now, nullable=False)
    approved_by = Column(String(20), ForeignKey("zup_employees.employee_id"), nullable=True)
    approved_at = Column(DateTime(), nullable=True)
    reject_reason = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default=WriteOffStatus.PENDING, index=True)

    # Relationships
    asset = relationship("Asset", foreign_keys=[asset_id], lazy="selectin")
    requester = relationship("Employee", foreign_keys=[requested_by], lazy="selectin")
    approver = relationship("Employee", foreign_keys=[approved_by], lazy="selectin")

    def __repr__(self):
        return f"<AssetWriteOff(id={self.write_off_id}, asset_id={self.asset_id}, status={self.status})>"