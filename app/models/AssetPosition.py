from typing import Optional
from app.models.Base import Base
from sqlalchemy import Column, Integer, ForeignKey, DateTime, Boolean, CheckConstraint
from sqlalchemy.orm import relationship, Mapped
from datetime import datetime


class AssetPosition(Base):
    """
    Модель позиции актива на карте цеха.
    Хранит координаты размещения активов на 2D карте.
    """
    __tablename__ = "asset_positions"

    # === Идентификатор ===
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # === Внешние ключи ===
    asset_id = Column(
        Integer,
        ForeignKey("assets.asset_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    workshop_id = Column(
        Integer,
        ForeignKey("workshops.workshop_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # === Координаты на карте ===
    x = Column(Integer, nullable=False)  # Координата X (пиксели)
    y = Column(Integer, nullable=False)  # Координата Y (пиксели)
    rotation = Column(
        Integer,
        default=0,
        nullable=False
    )  # Угол поворота (0-360 градусов)
    scale = Column(
        Integer,
        default=100,
        nullable=False
    )  # Масштаб иконки (проценты, 50-200)

    # === Статус ===
    is_active = Column(Boolean, default=True, index=True)  # Текущая позиция (для истории)

    # === Служебные поля ===
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # === Связи ===
    asset: Mapped[Optional["Asset"]] = relationship(
        "Asset",
        back_populates="asset_positions",
        lazy="joined"
    )

    workshop: Mapped[Optional["Workshop"]] = relationship(
        "Workshop",
        back_populates="asset_positions",
        lazy="joined"
    )

    # === Ограничения ===
    __table_args__ = (
        CheckConstraint('rotation >= 0 AND rotation < 360', name='check_rotation'),
        CheckConstraint('scale > 0', name='check_scale'),
        # Уникальный индекс: один актив может иметь только одну активную позицию
    )

    def __repr__(self):
        return f"<AssetPosition(id={self.id}, asset_id={self.asset_id}, workshop_id={self.workshop_id}, x={self.x}, y={self.y})>"