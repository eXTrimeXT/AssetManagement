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

    country = Column(String(100), index=True, default="Страна")
    city = Column(String(100), index=True, default="Город")
    address = Column(String(255), default="Улица и номер дома")
    room = Column(String(50), default="Номер помещения/кабинета")
    floor = Column(String(10), default="Этаж")

    # Связь с компаниями (одна локация может быть у нескольких компаний)
    companies: Mapped[List["Company"]] = relationship(
        "Company",
        back_populates="location_obj",
        lazy="select"
    )

    # Связь со складами (одна локация может иметь много складов)
    warehouses: Mapped[List["Warehouse"]] = relationship(
        "Warehouse",
        back_populates="location",
        lazy="select"
    )

    def __repr__(self):
        return f"<Location(id={self.location_id}, city={self.city}, address={self.address})>"