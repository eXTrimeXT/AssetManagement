# from sqlalchemy import Column, String, Date, DateTime, ForeignKey
# from sqlalchemy.orm import relationship
# from datetime import datetime
# from app.models.Base import Base
#
#
# class ZupDepartment(Base):
#     """Модель подразделения из 1С-ЗУП с иерархией"""
#     __tablename__ = "zup_departments"
#
#     guid = Column(String(36), primary_key=True, index=True)
#     name = Column(String(200), nullable=False, index=True)
#     name_en = Column(String(200))
#     short_name = Column(String(100), index=True)
#
#     creation_date = Column(Date)
#     closure_date = Column(Date, nullable=True)  # Пустая строка = активно
#
#     # Иерархия подразделений
#     # parent_guid = Column(String(36), ForeignKey("zup_departments.guid"), nullable=True, index=True)
#     parent_guid = Column(String(36), nullable=True, index=True)  # FK убран
#
#     created_at = Column(DateTime, default=datetime.now, nullable=False)
#     updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
#
#     # Relationships
#     # parent = relationship("ZupDepartment", remote_side=[guid], backref="children")
#     parent = relationship(
#         "ZupDepartment",
#         primaryjoin="ZupDepartment.parent_guid == remote(ZupDepartment.guid)",
#         remote_side="ZupDepartment.guid",
#         lazy="selectin",
#         backref="children"
#     )
#
#     employees = relationship(
#         "Employee",
#         primaryjoin="Employee.department_guid == ZupDepartment.guid",
#         foreign_keys="[Employee.department_guid]",
#         back_populates="department"
#     )
#     assignments = relationship("Assignment", back_populates="department")
#
#     def __repr__(self):
#         return f"<ZupDepartment(guid={self.guid}, name={self.name})>"
#
#     @property
#     def is_active(self) -> bool:
#         """Активно ли подразделение"""
#         return not self.closure_date
#
#     def get_hierarchy_path(self) -> list:
#         """Возвращает путь от корня до текущего подразделения"""
#         path = [self]
#         current = self.parent
#         while current:
#             path.insert(0, current)
#             current = current.parent
#         return path

from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship, remote
from datetime import datetime
from app.models.Base import Base


class ZupDepartment(Base):
    """Модель подразделения из 1С-ЗУП с иерархией"""
    __tablename__ = "zup_departments"

    guid = Column(String(36), primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    name_en = Column(String(200))
    short_name = Column(String(100), index=True)

    creation_date = Column(Date)
    closure_date = Column(Date, nullable=True)

    # Иерархия подразделений (БЕЗ FK!)
    parent_guid = Column(String(36), nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # === ЯВНО УКАЗАННЫЕ RELATIONSHIPS ===
    parent = relationship(
        "ZupDepartment",
        primaryjoin="ZupDepartment.parent_guid == remote(ZupDepartment.guid)",
        foreign_keys=[parent_guid],
        remote_side="ZupDepartment.guid",
        lazy="selectin",
        backref="children"
    )
    employees = relationship(
        "Employee",
        foreign_keys="Employee.department_guid",
        primaryjoin="Employee.department_guid == ZupDepartment.guid",
        back_populates="department"
    )
    assignments = relationship("Assignment", back_populates="department")

    def __repr__(self):
        return f"<ZupDepartment(guid={self.guid}, name={self.name})>"

    @property
    def is_active(self) -> bool:
        """Активно ли подразделение"""
        return not self.closure_date

    def get_hierarchy_path(self) -> list:
        """Возвращает путь от корня до текущего подразделения"""
        path = [self]
        current = self.parent
        while current:
            path.insert(0, current)
            current = current.parent
        return path