from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base

class AssetModel(Base):
    __tablename__ = "asset_models"

    model_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    model_name = Column(String(150), nullable=False, index=True) # Например: "Lenovo ThinkPad X1"

    class_id = Column(Integer, ForeignKey("asset_classes.class_id"), nullable=False, index=True)

    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False, index=True) # Активна ли модель в каталоге
    is_serial_required = Column(Boolean, default=True, nullable=False) # Обязателен ли серийный номер

    # Аудит
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Кто создал/изменил
    created_by = Column(Integer, ForeignKey("users.user_id"))
    updated_by = Column(Integer, ForeignKey("users.user_id"))

    # Связи
    asset_class = relationship("AssetClass", back_populates="models")
    catalog_items = relationship("AssetCatalog", back_populates="model", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

    def __repr__(self):
        return f"<AssetModel(id={self.model_id}, name={self.model_name})>"