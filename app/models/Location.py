from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base


class Location(Base):
    """Модель локации (местоположения)"""
    __tablename__ = "locations"

    location_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    country = Column(String(100))
    city = Column(String(100))
    address = Column(String(255))
    room = Column(String(50))
    floor = Column(String(10))

    created_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    creator = relationship("Employee", foreign_keys=[created_by])

    def __repr__(self):
        return f"<Location(id={self.location_id}, name={self.name})>"