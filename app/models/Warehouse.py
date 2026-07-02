from typing import List
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, Mapped
from app.models.Base import Base

class Warehouse(Base):
    """
    Модель склада.
    Хранит информацию о физических или логических складах компании.
    """
    __tablename__ = "warehouses"

    warehouse_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, index=True, unique=True)  # Название склада (уникальное)

    # Связь с локацией (адрес склада)
    location_id = Column(Integer, ForeignKey("locations.location_id"), index=True)

    # Ответственный за склад (ссылка на пользователя)
    prepared_by = Column(String(50), ForeignKey("users.user_tab_id"), index=True)

    # Обратные связи
    location = relationship("Location", back_populates="warehouses", lazy="joined")
    preparer = relationship("User", foreign_keys=[prepared_by], lazy="joined")

    # === НОВАЯ СВЯЗЬ: склад -> активы ===
    assets: Mapped[List["Asset"]] = relationship(
        "Asset",
        back_populates="warehouse_obj",
        lazy="select"
    )

    def __repr__(self):
        return f"<Warehouse(id={self.warehouse_id}, name={self.name})>"