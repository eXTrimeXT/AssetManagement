from typing import List
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship, Mapped
from app.models.Base import Base

class Department(Base):
    """
    Модель департамента.
    """
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    abbreviation = Column(String(50), nullable=False, unique=True, index=True)

    # Связь с отделами
    divisions: Mapped[List["Division"]] = relationship(
        "Division",
        back_populates="department",
        lazy="select"
    )

    def __repr__(self):
        return f"<Department(id={self.id}, name='{self.name}', abbreviation='{self.abbreviation}')>"