from typing import List

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship, Mapped
from app.models.Base import Base


class Location(Base):
    """
    Модель локации (местоположения).
    Хранит иерархическую структуру адресов: Страна -> Город -> Адрес -> Помещение -> Этаж.
    """
    __tablename__ = "locations"

    location_id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    country = Column(String(100), nullable=False, index=True, default="Страна")
    city = Column(String(100), nullable=False, index=True, default="Город")
    address = Column(String(255), nullable=False, default="Улица и номер дома")
    room = Column(String(50), nullable=True, default="Номер помещения/кабинета")
    floor = Column(String(10), nullable=True, default="Этаж")

    # Связь с активами (один ко многим: одна локация может иметь много активов)
    # Примечание: В модели Asset нужно будет добавить поле location_id и relationship,
    # если вы хотите связывать активы с этой таблицей напрямую вместо строкового поля.
    # Обратная связь: одна локация может иметь много активов
    assets: Mapped[List["Asset"]] = relationship(
        "Asset",
        back_populates="location_obj",
        lazy="select"
    )

    def __repr__(self):
        return f"<Location(id={self.location_id}, city={self.city}, address={self.address})>"