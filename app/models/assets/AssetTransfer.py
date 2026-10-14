from typing import Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from app.models.Base import Base


class AssetTransferStatus:
    """Статусы уведомлений"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"

    RU_LABELS = {
        PENDING: "в ожидании",
        ACCEPTED: "принято",
        DECLINED: "отклоненно",
        CANCELLED: "отмененно",
    }

    @classmethod
    def get_ru_label(cls, status: str) -> str:
        return cls.RU_LABELS.get(status, status)

class AssetTransfer(Base):
    __tablename__ = "asset_transfers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False)
    initiator_id = Column(String(10), ForeignKey("zup_employees.employee_id"), nullable=False)
    target_employee_id = Column(String(10), ForeignKey("zup_employees.employee_id"), nullable=False)
    assignment_type = Column(String(20), nullable=False)  # 'user' или 'responsible'
    status = Column(String(20), nullable=False, default=AssetTransferStatus.PENDING)  # PENDING, ACCEPTED, DECLINED, CANCELLED
    initiator_comment = Column(Text, nullable=True)
    responder_comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True)

    # Индексы для производительности
    __table_args__ = (
        Index("ix_asset_transfers_target_status", "target_employee_id", "status"),
        Index("ix_asset_transfers_initiator", "initiator_id"),
    )

    def __repr__(self):
        return f"<AssetTransfer(id={self.id}, asset_id={self.asset_id}, status={self.status})>"

    @property
    def status_ru(self) -> Optional[str]:
        if not self.status:
            return None
        return AssetTransferStatus.get_ru_label(self.status)