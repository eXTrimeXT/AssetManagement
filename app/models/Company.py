from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base


class Company(Base):
    """Модель компании"""
    __tablename__ = "companies"

    company_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_name = Column(String(255), unique=True, nullable=False, index=True)
    gen_director = Column(String(150))
    phone_number = Column(String(50))

    # Связь с локацией
    location_id = Column(Integer, ForeignKey("locations.location_id"), index=True, nullable=True)

    # Аудит
    created_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    location_obj = relationship("Location", foreign_keys=[location_id])
    creator = relationship("Employee", foreign_keys=[created_by])
    vendors = relationship("Vendor", back_populates="company")

    def __repr__(self):
        return f"<Company(id={self.company_id}, name={self.company_name})>"