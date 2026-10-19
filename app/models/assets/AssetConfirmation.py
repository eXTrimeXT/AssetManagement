from typing import Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.models.Base import Base

class AssetConfirmationStatus:
    PENDING = "pending"
    CONFIRMED = "confirmed"
    NOT_FOUND = "not_found"
    DAMAGED = "damaged"

    RU_LABELS = {
        PENDING: "В ожидании",
        CONFIRMED: "Подтвержденный",
        NOT_FOUND: "Не найдено",
        DAMAGED: "Поврежденный",
    }

    @classmethod
    def get_ru_label(cls, status: str) -> str:
        return cls.RU_LABELS.get(status, status)

class AssetConfirmation(Base):
    __tablename__ = "asset_confirmations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(String(20), ForeignKey("zup_employees.employee_id"), nullable=False)
    requested_by = Column(String(20), ForeignKey("zup_employees.employee_id"), nullable=True)

    status = Column(String(20), default=AssetConfirmationStatus.PENDING, nullable=False)
    comment = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def status_ru(self) -> Optional[str]:
        if not self.status:
            return None
        return AssetConfirmationStatus.get_ru_label(self.status)