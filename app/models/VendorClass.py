from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base


class VendorClass(Base):
    """Модель класса поставщика"""
    __tablename__ = "vendor_classes"

    class_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(300))

    created_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    creator = relationship("Employee", foreign_keys=[created_by])
    vendors = relationship("Vendor", back_populates="vendor_class")

    def __repr__(self):
        return f"<VendorClass(id={self.class_id}, name={self.name})>"