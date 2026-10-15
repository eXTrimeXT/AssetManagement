from typing import Optional
from pydantic import computed_field
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.Base import Base


class AssetHistoryActionType:
    CREATE = "create"
    UPDATE= "update"
    DELETE = "delete"
    ASSIGN = "assign"
    UNASSIGN = "unassign"
    MOVE = "move"
    STATUS_CHANGE = "status_change"

    RU_LABELS = {
        CREATE: "создание",
        UPDATE: "обновление",
        DELETE: "удаление",
        ASSIGN: "привязка",
        UNASSIGN: "отмена привязки",
        MOVE: "изменение местоположения",
        STATUS_CHANGE: "изменение статуса",
    }

    @classmethod
    def get_ru_label(cls, action: str) -> str:
        return cls.RU_LABELS.get(action, action)

class AssetHistory(Base):
    __tablename__ = "asset_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="SET NULL"), nullable=True, index=True)

    # Тип действия
    action_type = Column(
        String(50),
        nullable=False,
        default=AssetHistoryActionType.UPDATE,
        index=True
    )  # create, update, delete, assign, unassign, move, status_change

    field_name = Column(String(100), nullable=True)  # Может быть NULL для create/delete
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    # Аудит
    changed_by = Column(String(20), ForeignKey("zup_employees.employee_id"), nullable=False)
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    comment = Column(Text, nullable=True)  # Комментарий к изменению

    # Группировка (для объединения нескольких изменений в одну операцию)
    session_id = Column(String(36), nullable=True, index=True)  # UUID

    # Relationships
    changer = relationship("Employee", foreign_keys=[changed_by], lazy="selectin")

    @computed_field
    @property
    def changer_full_name_ru(self) -> Optional[str]:
        """ФИО изменившего на русском"""
        if not self.changer:
            return None
        parts = [p for p in [self.changer.last_name, self.changer.first_name, self.changer.middle_name] if p]
        return " ".join(parts) if parts else None

    @computed_field
    @property
    def changer_full_name_en(self) -> Optional[str]:
        """ФИО изменившего на английском"""
        if not self.changer:
            return None
        parts = [p for p in [self.changer.last_name_en, self.changer.first_name_en, self.changer.middle_name_en] if p]
        return " ".join(parts) if parts else None

    @property
    def event_type_ru(self) -> Optional[str]:
        if not self.action_type:
            return None
        return AssetHistoryActionType.get_ru_label(self.action_type)

    def __repr__(self):
        return f"<AssetHistory(id={self.id}, asset_id={self.asset_id}, action={self.action_type}, field={self.field_name})>"