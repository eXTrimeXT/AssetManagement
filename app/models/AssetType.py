from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer
from app.models.Base import Base

class AssetType(Base):
    """
    Модель справочника типов активов.
    Справочник типов оборудования (Компьютеры, Серверы, Сетевое оборудование и т.д.).
    """
    __tablename__ = "asset_types"

    # Уникальный идентификатор записи (Primary Key)
    asset_type_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Человекочитаемое название типа (например, "Ноутбук")
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Бизнес-код типа (например, 10, 20, 30)
    # unique=True обязателен, так как на это поле ссылается внешний ключ в таблице Asset
    type_id: Mapped[int] = mapped_column(Integer, index=True, unique=True, nullable=False)

    # Связь "Один ко многим": один тип может иметь много активов
    # Используем строковую ссылку "Asset" вместо прямого импорта
    assets: Mapped[list["Asset"]] = relationship(
        back_populates="asset_type",
        lazy="selectin"
    )