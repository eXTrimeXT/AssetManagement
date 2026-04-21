from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base

class CatalogOperation(Base):
    __tablename__ = "catalog_operations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # ВАЖНО: Нет ondelete="CASCADE". История должна жить своей жизнью.
    # catalog_id = Column(Integer, ForeignKey("asset_catalog.catalog_id", ondelete="SET NULL"), nullable=False, index=True)
    catalog_id = Column(Integer, nullable=True, index=True)

    # === СНАПШОТЫ (Копии данных на момент операции) ===
    asset_inventory_id_snapshot = Column(String(50), index=True) # Инвентарный номер
    model_name_snapshot = Column(String(150))                    # Название модели
    class_name_snapshot = Column(String(100))                    # Название класса
    warehouse_name_snapshot = Column(String(100))                # Название склада
    owner_name_snapshot = Column(String(150))                    # ФИО владельца

    operation_type = Column(String(50), nullable=False)

    # Полные данные в JSON (для глубокого аудита)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)

    performed_by = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    performer = relationship("User", foreign_keys=[performed_by], lazy="joined")

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    comment = Column(String(255), nullable=True)