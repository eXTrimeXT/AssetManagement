from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base

class AssetCatalog(Base):
    __tablename__ = "asset_catalog"

    catalog_id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Связи со справочниками
    class_id = Column(Integer, ForeignKey("asset_classes.class_id"), nullable=False, index=True)
    model_id = Column(Integer, ForeignKey("asset_models.model_id"), nullable=False, index=True)

    # Связь с конкретным активом (Instance)
    # Один запись в каталоге = один физический актив (или группа, если не сериализовано, но у вас serial_id теперь nullable)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), unique=True, nullable=False, index=True)

    # Владелец (дублируем или синхронизируем с текущим статусом актива, но здесь исторический владелец записи в каталоге)
    owner_id = Column(Integer, ForeignKey("users.user_id"), index=True)

    # Склад
    warehouse_id = Column(Integer, ForeignKey("warehouses.warehouse_id"))

    # Гарантия
    warranty_end_date = Column(Date)

    # Аудит
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.user_id"))

    # Связи
    model = relationship("AssetModel", back_populates="catalog_items")
    asset = relationship("Asset", backref="catalog_entry", uselist=False) # Обратная связь один к одному
    owner = relationship("User", foreign_keys=[owner_id])
    creator = relationship("User", foreign_keys=[created_by])
    warehouse = relationship("Warehouse", foreign_keys=[warehouse_id])

    def __repr__(self):
        return f"<AssetCatalog(catalog_id={self.catalog_id}, asset_id={self.asset_id})>"