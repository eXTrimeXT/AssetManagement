from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float
from sqlalchemy.orm import relationship, Mapped
from datetime import datetime

from app.models.Base import Base


class Workshop(Base):
    """
    Модель цеха/участка.
    Хранит информацию о производственных цехах и их картах.
    """
    __tablename__ = "workshops"

    # === Идентификатор ===
    workshop_id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # === Основные поля ===
    name = Column(String(255), nullable=False, index=True)  # Название цеха
    code = Column(String(50), unique=True, index=True)  # Код цеха (например "ЦЕХ-001")
    description = Column(Text, nullable=True)  # Описание цеха

    # === Карта цеха ===
    background_image_url = Column(String(500), nullable=True)  # Путь к фону (плану цеха)

    # === ГЕОМЕТРИЯ ЦЕХА (для сложных форм: Г-образные, П-образные и т.д.) ===
    geometry = Column(JSONB, nullable=True)

    # Если нет геометрии и это простая прямоугольная фигура
    workshop_width = Column(Integer, nullable=True)  # Ширина цеха
    workshop_height = Column(Integer, nullable=True)  # Высота цеха

    # === ПОЗИЦИЯ НА ОБЩЕЙ КАРТЕ (для относительных координат активов) ===
    offset_x = Column(Integer, default=0, server_default="0")  # Смещение по X на общей карте
    offset_y = Column(Integer, default=0, server_default="0")  # Смещение по Y на общей карте

    # === МАСШТАБ ЦЕХА ===
    workshop_scale = Column(Float, default=1.0, server_default="1.0")

    # === ЦВЕТ ЦЕХА (hex формат: #RRGGBB или #RRGGBBAA) ===
    color = Column(String(20), default="#546E7A", server_default="#546E7A", nullable=True)

    # === Статус ===
    is_active = Column(Boolean, default=True, index=True)  # Активен ли цех

    # === Служебные поля ===
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # === Связи ===
    # assets: Mapped[list["Asset"]] = relationship(
    #     "Asset",
    #     back_populates="workshop",
    #     lazy="select"
    # )

    asset_positions: Mapped[list["AssetPosition"]] = relationship(
        "AssetPosition",
        back_populates="workshop",
        lazy="select",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Workshop {self.workshop_id}: {self.name}>"