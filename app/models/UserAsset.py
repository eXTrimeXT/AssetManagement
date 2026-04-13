from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime, String
from sqlalchemy.orm import relationship
from app.models.Base import Base

class UserAsset(Base):
    """
    Ассоциативная таблица Many-to-Many: Пользователи <-> Активы.
    Хранит историю назначений и возвратов.
    """
    __tablename__ = "user_assets"

    assign_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False, index=True)

    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    returned_at = Column(DateTime, nullable=True, index=True)  # NULL = актив сейчас у пользователя

    # Отношения
    user = relationship("User", back_populates="assignments", lazy="joined")
    asset = relationship("Asset", back_populates="user_assignments", lazy="joined")