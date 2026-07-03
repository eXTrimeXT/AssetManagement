from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base


class Vendor(Base):
    """Модель поставщика/производителя"""
    __tablename__ = "vendors"

    vendor_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(150), nullable=False, index=True)
    supplier_number = Column(String(50), unique=True, index=True)
    contact_person = Column(String(150))
    phone = Column(String(50))
    email = Column(String(100))
    address = Column(String(300))
    description = Column(String(500))

    # Связи
    company_id = Column(Integer, ForeignKey("companies.company_id"), index=True)
    vendor_class_id = Column(Integer, ForeignKey("vendor_classes.class_id"), index=True)

    created_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    company = relationship("Company", back_populates="vendors")
    vendor_class = relationship("VendorClass", back_populates="vendors")
    creator = relationship("Employee", foreign_keys=[created_by])

    def __repr__(self):
        return f"<Vendor(id={self.vendor_id}, name={self.name})>"