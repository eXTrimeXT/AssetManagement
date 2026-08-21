from typing import Optional
from sqlalchemy import Column, Integer, ForeignKey, DateTime, Boolean, CheckConstraint, String
from sqlalchemy.orm import relationship, Mapped
from datetime import datetime

from app.models.Base import Base


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
    rotation = Column(Integer, default=0, nullable=False)  # Угол поворота (0-360 градусов)
    scale = Column(Integer, default=100, nullable=False)  # Масштаб иконки (проценты, 50-200)

    # === Статус ===
    is_active = Column(Boolean, default=True, index=True)  # Текущая позиция (для истории)

    # Линия, офис, помещение и этаж
    place = Column(String(100), nullable=True)  # Линия (1-07)
    level = Column(Integer, default=0)          # Этаж (2 Этаж)

    # === Служебные поля ===
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

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

    def __repr__(self) -> str:
        return f"<AssetPosition {self.id}: asset_id={self.asset_id}, x={self.x}, y={self.y}>"