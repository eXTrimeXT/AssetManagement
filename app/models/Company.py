from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, Mapped
from typing import Optional
from app.models.Base import Base


class Company(Base):
    """
    Таблица компаний (юридических лиц).
    Хранит общую информацию о контрагентах.
    """
    __tablename__ = "companies"

    company_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_name = Column(String(255), nullable=False, index=True)  # Название компании
    gen_director = Column(String(150))  # Генеральный директор (ФИО)
    phone_number = Column(String(50))   # Телефон компании

    # Ссылка на локацию (адрес компании) - опционально
    location_id = Column(Integer, ForeignKey("locations.location_id"), index=True)
    location_obj: Mapped[Optional["Location"]] = relationship(
        "Location",
        back_populates="companies",
        lazy="joined" # Подгружаем локацию сразу при запросе актива
    )

    # Обратная связь с таблицей вендоров/поставщиков
    vendors = relationship("Vendor", back_populates="company", lazy="selectin")

    def __repr__(self):
        return f"<Company(id={self.company_id}, name='{self.company_name}')>"