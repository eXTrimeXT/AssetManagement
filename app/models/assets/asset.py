from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship, backref
from datetime import datetime
from app.models.Base import Base


class Asset(Base):
    __tablename__ = "assets"

    asset_id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Основные поля
    name = Column(String(150), nullable=False, index=True)
    inventory_id = Column(String(100), unique=True, index=True, nullable=False)
    serial_number = Column(String(100), unique=True, index=True, nullable=True)
    asset_status = Column(String(100), index=True, default="Приемка")
    comment = Column(Text)

    # Даты
    date_issue = Column(Date)
    date_purchasing = Column(Date)

    # Связи
    model_id = Column(Integer, ForeignKey("asset_models.model_id"), index=True)
    asset_type_id = Column(Integer, ForeignKey("asset_types.asset_type_id"), index=True)
    parent_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), index=True)
    location_id = Column(Integer, ForeignKey("locations.location_id"), index=True)

    # Ответственные
    prepared_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    checked_by = Column(String(20), ForeignKey("zup_employees.employee_id"))

    # Аудит
    created_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    updated_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    model = relationship("AssetModel", back_populates="assets")
    asset_type = relationship("AssetType", back_populates="assets")
    parent = relationship(
        "Asset",
        remote_side=[asset_id],
        backref=backref("children", lazy="selectin", cascade="all, delete-orphan"),
        lazy="selectin"
    )
    location = relationship("Location", back_populates="assets")

    assignments = relationship(
        "AssetAssignment",
        back_populates="asset",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    preparer = relationship("Employee", foreign_keys=[prepared_by])
    checker = relationship("Employee", foreign_keys=[checked_by])
    creator = relationship("Employee", foreign_keys=[created_by])
    updater = relationship("Employee", foreign_keys=[updated_by])

    def __repr__(self):
        return f"<Asset(id={self.asset_id}, name={self.name})>"