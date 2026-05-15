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

    # Название типа (теперь должно быть уникальным, чтобы заменять логику type_id)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)

    # Связь с активами
    # assets: Mapped[list["Asset"]] = relationship(
    #     back_populates="asset_type",
    #     lazy="selectin"
    # )