from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base

class Company(Base):
    """Модель компании"""
    __tablename__ = "sap_departments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    department_code = Column(String(100), unique=True, nullable=False, index=True)
    department = Column(String(50))
    department_name = Column(String(200))
    parent_department = Column(String(50))
