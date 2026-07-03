from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base


class AssetClass(Base):
    __tablename__ = "asset_classes"

    class_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    class_name = Column(String(100), nullable=False, index=True)
    description = Column(String(500))

    asset_type_id = Column(Integer, ForeignKey("asset_types.asset_type_id"), nullable=False, index=True)

    created_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    updated_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    asset_type = relationship("AssetType", back_populates="asset_classes")
    creator = relationship("Employee", foreign_keys=[created_by])
    updater = relationship("Employee", foreign_keys=[updated_by])
    asset_models = relationship("AssetModel", back_populates="asset_class", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AssetClass(id={self.class_id}, name={self.class_name})>"