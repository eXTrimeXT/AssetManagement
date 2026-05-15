from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base

class AssetCatalog(Base):
    """
    Модель каталога активов.
    Связывает конкретный физический актив с владельцем и гарантией.
    """
    __tablename__ = "asset_catalog"

    catalog_id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Связь с конкретным активом (Instance)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), unique=False, nullable=False, index=True)

    # Владелец (дублируем или синхронизируем с текущим статусом актива, но здесь исторический владелец записи в каталоге)
    owner_id = Column(Integer, ForeignKey("users.user_id"), index=True)

    # Гарантия
    warranty_end_date = Column(Date)

    # Аудит
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.user_id"))

    # Связи
    asset = relationship("Asset", backref="catalog_entry", uselist=False) # Обратная связь один к одному
    owner = relationship("User", foreign_keys=[owner_id])
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        return f"<AssetCatalog(catalog_id={self.catalog_id}, asset_id={self.asset_id})>"