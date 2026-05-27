from typing import List
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, Mapped
from app.models.Base import Base

class Division(Base):
    """
    Модель отдела.
    """
    __tablename__ = "divisions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    abbreviation = Column(String(50), nullable=False, unique=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)

    # Связи
    department: Mapped["Department"] = relationship("Department", back_populates="divisions")
    groups: Mapped[List["Group"]] = relationship(
        "Group",
        back_populates="division",
        lazy="select"
    )

    def __repr__(self):
        return f"<Division(id={self.id}, name='{self.name}', abbreviation='{self.abbreviation}')>"