from tokenize import String

from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base

class AssetCatalog(Base):
    """
    Связывает конкретный физический актив с владельцем и гарантией.
    Смысл: можно привязать 1 актив на несколько пользователей
    """
    __tablename__ = "asset_catalog"

    catalog_id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Связь с конкретным активом
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), unique=False, nullable=True, index=True)

    # Связь с android
    android_id = Column(String, ForeignKey("android_data.android_id"), unique=False, nullable=True, index=True)

    # Владелец (дублируем или синхронизируем с текущим статусом актива, но здесь исторический владелец записи в каталоге)
    owner_id = Column(Integer, ForeignKey("users.user_id"), index=True)

    # Аудит
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.user_id"))

    # Связи
    asset = relationship("Asset", backref="catalog_entry", uselist=False) # Обратная связь один к одному
    android_data = relationship(
        "AndroidData",
        primaryjoin="AssetCatalog.android_id == foreign(AndroidData.android_id)",
        backref="catalog_entries",
        uselist=False,
        lazy="joined"
    )
    owner = relationship("User", foreign_keys=[owner_id])
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        return f"<AssetCatalog(catalog_id={self.catalog_id}, asset_id={self.asset_id})>, android_id={self.android_id})>"