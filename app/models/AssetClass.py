from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base

class AssetClass(Base):
    __tablename__ = "asset_classes"

    class_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    class_name = Column(String(100), nullable=False, index=True) # Например: "Ноутбук"

    # Ссылка на справочник типов (type_id из AssetType)
    class_type_id = Column(Integer, ForeignKey("asset_types.asset_type_id"), nullable=False, index=True)

    description = Column(Text)

    # Аудит
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Кто создал/изменил (ссылка на user_id)
    created_by = Column(Integer, ForeignKey("users.user_id"))
    updated_by = Column(Integer, ForeignKey("users.user_id"))

    # Связи
    # Связь с типом актива
    asset_type = relationship("AssetType", foreign_keys=[class_type_id], lazy="joined")

    # Связь с моделями оборудования
    models = relationship("AssetModel", back_populates="asset_class", cascade="all, delete-orphan")

    # Связь с пользователями (Создатель и обновляющий)
    creator = relationship("User", foreign_keys=[created_by], lazy="joined")
    updater = relationship("User", foreign_keys=[updated_by], lazy="joined")

    def __repr__(self):
        return f"<AssetClass(id={self.class_id}, name={self.class_name})>"