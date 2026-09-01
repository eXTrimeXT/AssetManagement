from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
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
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    creator = relationship("Employee", foreign_keys=[created_by])
    # assets = relationship("Asset", back_populates="location")

    def __repr__(self):
        return f"<Location(id={self.location_id}, name={self.name})>"