from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint, func, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, date
from app.models.Base import Base

class AssignmentTypeEnum(str, Enum):
    USER = "user"
    RESPONSIBLE = "responsible"
    SERVING = "serving"
    USER_DECLINED = "user_declined"

class AssetAssignment(Base):
    """Связь актива с пользователем (история назначений)"""
    __tablename__ = "asset_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Связи
    asset_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(String(20), ForeignKey("zup_employees.employee_id"), nullable=False, index=True)

    # Тип назначения: AssignmentTypeEnum
    assignment_type = Column(String(20), nullable=False, default=AssignmentTypeEnum.USER, index=True)


    # Временные рамки
    start_date = Column(Date, nullable=False, default=date.today, index=True)
    end_date = Column(Date, nullable=True, index=True)  # NULL = активная связь

    # Аудит
    assigned_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    comment = Column(String(500))
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Защита от дубликатов: нельзя назначить одного сотрудника на один актив дважды (по типу)
    __table_args__ = (
        UniqueConstraint('asset_id', 'employee_id', 'assignment_type', 'end_date', name='uq_asset_employee_type_active'),
    )

    # Relationships
    asset = relationship("Asset", back_populates="assignments")
    employee = relationship("Employee", foreign_keys=[employee_id])
    assigner = relationship("Employee", foreign_keys=[assigned_by])

    def __repr__(self):
        return f"<AssetAssignment(asset={self.asset_id}, employee={self.employee_id}, active={self.end_date is None})>"