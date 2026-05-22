from typing import List

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer
from app.models.Base import Base

class AssetType(Base):
    """
    Модель справочника типов активов.
    type_id удален. Теперь используется только asset_type_id (autoincrement).
    """
    __tablename__ = "asset_types"

    # Первичный ключ (автоинкремент)
    asset_type_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Название типа должно быть уникальным
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)

    # Название на английском (необходимо для назначения прав по типу актива)
    en_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)

    # Обратная связь: у типа может быть много классов
    asset_classes: Mapped[List["AssetClass"]] = relationship("AssetClass", back_populates="asset_type", lazy="selectin")