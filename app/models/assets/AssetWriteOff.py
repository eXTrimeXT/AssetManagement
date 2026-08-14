from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.Base import Base

class AssetWriteOff(Base):
    __tablename__ = "asset_write_offs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Связь с активом
    asset_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False, index=True)

    # Причина
    reason = Column(String(50), nullable=False)  # broken, obsolete, lost, stolen, disposed
    reason_description = Column(Text, nullable=True)

    # Документ
    act_number = Column(String(100), unique=True, nullable=False, index=True)
    act_date = Column(Date, nullable=False)

    # Метод утилизации
    disposal_method = Column(String(50), nullable=True)  # recycled, disposed, sold, returned

    # Инициатор
    initiated_by = Column(String(20), ForeignKey("zup_employees.employee_id"), nullable=False)

    # Примечания
    notes = Column(Text, nullable=True)

    # Дата списания
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    asset = relationship("Asset", back_populates="write_offs")