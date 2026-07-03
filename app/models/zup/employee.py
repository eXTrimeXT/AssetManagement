from sqlalchemy import Column, String, Date, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base


class Employee(Base):
    """Модель сотрудника из 1С-ЗУП"""
    __tablename__ = "zup_employees"

    # Уникальные идентификаторы из 1С
    guid = Column(String(36), primary_key=True, index=True)  # UUID из 1С
    guid_person = Column(String(36), index=True)  # Ссылка на физическое лицо

    # Табельный номер (10 цифр минимум)
    employee_id = Column(String(20), unique=True, index=True, nullable=False)

    # ФИО на русском
    last_name = Column(String(100), index=True)
    first_name = Column(String(100), index=True)
    middle_name = Column(String(100))

    # ФИО на английском
    last_name_en = Column(String(100))
    first_name_en = Column(String(100))
    middle_name_en = Column(String(100))

    # Даты
    birth_date = Column(Date)
    employment_date = Column(Date)
    dismissal_date = Column(Date, nullable=True)  # Пустая строка = действующий

    # Контакты
    phone = Column(String(20))
    email = Column(String(100), index=True)

    # Связи с должностью и подразделением
    position_guid = Column(String(36), index=True)
    department_guid = Column(String(36), index=True)

    # Служебные поля
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    position = relationship(
        "Position",
        primaryjoin="Employee.position_guid == Position.guid",
        foreign_keys=[position_guid],
        back_populates="employees"
    )
    department = relationship(
        "ZupDepartment",
        primaryjoin="Employee.department_guid == ZupDepartment.guid",
        foreign_keys=[department_guid],
        back_populates="employees"
    )
    managers_as_employee = relationship(
        "Manager",
        foreign_keys="Manager.guid_employee",
        back_populates="employee"
    )
    managers_as_manager = relationship(
        "Manager",
        foreign_keys="Manager.guid_manager",
        back_populates="manager"
    )
    assignments = relationship("Assignment", back_populates="employee")

    def __repr__(self):
        return f"<Employee(id={self.employee_id}, name={self.last_name} {self.first_name})>"

    @property
    def full_name_ru(self) -> str:
        """Полное ФИО на русском"""
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(filter(None, parts))

    @property
    def full_name_en(self) -> str:
        """Полное ФИО на английском"""
        parts = [self.last_name_en, self.first_name_en, self.middle_name_en]
        return " ".join(filter(None, parts))