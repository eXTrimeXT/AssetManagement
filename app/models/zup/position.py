from sqlalchemy import Column, String, Date, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base


class Position(Base):
    """Модель должности из 1С-ЗУП"""
    __tablename__ = "zup_positions"

    guid = Column(String(36), primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    name_en = Column(String(200))

    creation_date = Column(Date)
    expiration_date = Column(Date, nullable=True)  # Пустая строка = активна

    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    employees = relationship(
        "Employee",
        primaryjoin="Employee.position_guid == Position.guid",
        foreign_keys="[Employee.position_guid]",
        back_populates="position"
    )
    assignments = relationship("Assignment", back_populates="position")

    def __repr__(self):
        return f"<Position(guid={self.guid}, name={self.name})>"

    @property
    def is_active(self) -> bool:
        """Активна ли должность"""
        return not self.expiration_date