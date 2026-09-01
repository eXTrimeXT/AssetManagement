from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base

class AssetType(Base):
    __tablename__ = "asset_types"

    asset_type_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    en_name = Column(String(100), unique=True, nullable=False, index=True)
    created_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    creator = relationship("Employee", foreign_keys=[created_by])
    assets = relationship("Asset", back_populates="asset_type", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AssetType(id={self.asset_type_id}, name={self.name})>"