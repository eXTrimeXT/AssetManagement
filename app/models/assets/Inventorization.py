from sqlalchemy import Column, Integer, Boolean, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.Base import Base

class InventorizationSession(Base):
    __tablename__ = "inventorization_sessions"
    session_id = Column(Integer, primary_key=True, index=True)
    asset_type_id = Column(Integer, ForeignKey("asset_types.asset_type_id"), nullable=False)
    asset_type_name = Column(String(100), nullable=False)
    asset_type_en_name = Column(String(100), nullable=False)
    status = Column(String(50), default="in_progress")  # in_progress, completed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("InventorizationItem", back_populates="session")
    asset_type = relationship("AssetType", foreign_keys=[asset_type_id])

class InventorizationItem(Base):
    __tablename__ = "inventorization_items"

    inventorization_id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("inventorization_sessions.session_id"), nullable=False)
    asset_id = Column(Integer, nullable=False)  # Без ForeignKey, чтобы удаление из assets не ломало запись здесь
    asset_name = Column(String(150), nullable=False)
    asset_inventory_id = Column(String(100), nullable=False)
    asset_serial_number = Column(String(100), nullable=True)
    is_checked = Column(Boolean, default=False)

    session = relationship("InventorizationSession", back_populates="items")