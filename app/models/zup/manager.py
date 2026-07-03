from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base


class Manager(Base):
    """Модель связи сотрудник-руководитель из 1С-ЗУП"""
    __tablename__ = "zup_managers"

    id = Column(String(100), primary_key=True, index=True)  # UUID связи

    guid_employee = Column(String(100), ForeignKey("zup_employees.guid"), nullable=False, index=True)
    guid_manager = Column(String(100), ForeignKey("zup_employees.guid"), nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    employee = relationship("Employee", foreign_keys=[guid_employee], back_populates="managers_as_employee")
    manager = relationship("Employee", foreign_keys=[guid_manager], back_populates="managers_as_manager")

    def __repr__(self):
        return f"<Manager(employee={self.guid_employee}, manager={self.guid_manager})>"