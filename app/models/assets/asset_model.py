from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base


class AssetModel(Base):
    __tablename__ = "asset_models"

    model_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    model_name = Column(String(150), nullable=False, index=True)
    description = Column(String(500))

    class_id = Column(Integer, ForeignKey("asset_classes.class_id"), nullable=False, index=True)

    created_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    updated_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    asset_class = relationship("AssetClass", back_populates="asset_models")
    creator = relationship("Employee", foreign_keys=[created_by])
    updater = relationship("Employee", foreign_keys=[updated_by])
    assets = relationship("Asset", back_populates="model", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AssetModel(id={self.model_id}, name={self.model_name})>"