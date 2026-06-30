from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base


class VendorClass(Base):
    """
    Справочник классов контрагентов (производители, вендоры, поставщики).
    """
    __tablename__ = "vendor_classes"

    vendor_class_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)

    created_at = Column(DateTime, default=datetime.now, nullable=False)

    # Обратная связь с таблицей компаний/контрагентов
    vendors = relationship("Vendor", back_populates="vendor_class", lazy="selectin")

    def __repr__(self):
        return f"<VendorClass(id={self.vendor_class_id}, name='{self.name}')>"