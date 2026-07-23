from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base

class AssetModel(Base):
    __tablename__ = "asset_models"

    model_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(150), nullable=False, index=True)
    description = Column(Text)

    asset_type_id = Column(Integer, ForeignKey("asset_types.asset_type_id"), index=True, nullable=True)

    created_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    updated_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    asset_type = relationship("AssetType")

    assets = relationship("Asset", back_populates="model", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AssetModel(id={self.model_id}, name={self.name})>"