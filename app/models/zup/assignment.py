from sqlalchemy import Column, String, Date, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base


class Assignment(Base):
    """Модель назначения (история кадровых изменений) из 1С-ЗУП"""
    __tablename__ = "zup_assignments"

    id = Column(String(36), primary_key=True, index=True)  # UUID назначения

    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=True, index=True)  # Пустая строка = действует сейчас

    # Связи
    employee_guid = Column(String(36), ForeignKey("zup_employees.guid"), nullable=False, index=True)
    department_guid = Column(String(36), ForeignKey("zup_departments.guid"), nullable=False, index=True)
    position_guid = Column(String(36), ForeignKey("zup_positions.guid"), nullable=False, index=True)

    # Ставка (Full-Time Equivalent)
    fte = Column(Numeric(5, 2), default=1.0)  # 1.0 = полная ставка, 0.5 = полставки

    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    employee = relationship(
        "Employee",
        primaryjoin="Assignment.employee_guid == Employee.guid",
        foreign_keys=[employee_guid],
        back_populates="assignments"
    )
    department = relationship(
        "ZupDepartment",
        primaryjoin="Assignment.department_guid == ZupDepartment.guid",
        foreign_keys=[department_guid],
        back_populates="assignments"
    )
    position = relationship(
        "Position",
        primaryjoin="Assignment.position_guid == Position.guid",
        foreign_keys=[position_guid],
        back_populates="assignments"
    )

    def __repr__(self):
        return f"<Assignment(employee={self.employee_guid}, position={self.position_guid})>"

    @property
    def is_current(self) -> bool:
        """Действует ли назначение сейчас"""
        return not self.end_date