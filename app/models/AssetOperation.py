from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base


class AssetOperation(Base):
    """
    Модель для хранения истории операций с активами.
    Хранит копию ключевых данных актива, чтобы история была доступна даже после удаления актива.
    """
    __tablename__ = "asset_operations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Ссылка на актив (может стать NULL или вести в никуда после hard delete,
    # но мы сохраняем её для активных активов)
    asset_id = Column(Integer, nullable=True, index=True)

    # === КОПИЯ ДАННЫХ АКТИВА (для истории удалений) ===
    inventory_id_snapshot = Column(String(50), index=True)  # Инвентарный номер на момент операции
    name_snapshot = Column(String(150))                     # Название на момент операции

    # Тип операции
    operation_type = Column(String(50), nullable=False)     # CREATE, UPDATE, DELETE, DEACTIVATE...

    # Детали изменений
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)

    # Кто выполнил
    performed_by = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    performer = relationship("User", foreign_keys=[performed_by], lazy="joined")

    # Время
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Комментарий
    comment = Column(String(255), nullable=True)

    def __repr__(self):
        return f"<AssetOperation(id={self.id}, inv_id={self.inventory_id_snapshot}, type={self.operation_type})>"