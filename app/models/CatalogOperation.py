from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base

class CatalogOperation(Base):
    """
    Модель для хранения истории операций с записями каталога активов.
    """
    __tablename__ = "catalog_operations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Ссылка на запись в каталоге
    catalog_id = Column(Integer, ForeignKey("asset_catalog.catalog_id", ondelete="CASCADE"), nullable=False, index=True)

    # Снимок основных данных записи каталога (для отображения в истории даже после удаления)
    asset_inventory_id_snapshot = Column(String(50), index=True) # Инвентарный номер актива
    model_name_snapshot = Column(String(150))                    # Название модели
    class_name_snapshot = Column(String(100))                    # Название класса

    # Тип операции: CREATE, UPDATE, DELETE, ASSIGN_OWNER, MOVE_WAREHOUSE
    operation_type = Column(String(50), nullable=False)

    # Старые и новые значения (JSONB)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)

    # Кто выполнил операцию
    performed_by = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    performer = relationship("User", foreign_keys=[performed_by], lazy="joined")

    # Время операции
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Комментарий
    comment = Column(String(255), nullable=True)

    def __repr__(self):
        return f"<CatalogOperation(id={self.id}, catalog_id={self.catalog_id}, type={self.operation_type})>"