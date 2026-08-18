from typing import Optional, List

from pydantic import computed_field
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship, backref, Mapped
from datetime import datetime
from app.models.Base import Base
from app.schemas.assets.AssetAssignmentSchemas import AssetUserResponse

class Asset(Base):
    __tablename__ = "assets"

    asset_id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Основные поля
    name = Column(String(150), nullable=False, index=True)
    inventory_id = Column(String(100), unique=True, index=True, nullable=False)
    serial_number = Column(String(100), unique=True, index=True, nullable=True)
    asset_status_id = Column(Integer, ForeignKey("asset_status.id"), nullable=True)
    quantity = Column(Integer, default=1, nullable=True)
    comment = Column(Text)

    # Даты
    date_issue = Column(Date)
    date_purchasing = Column(Date)

    # Связи
    model_id = Column(Integer, ForeignKey("asset_models.model_id"), index=True)
    model_name = Column(String(300), nullable=True)

    # Временные текстовые поля
    parent_name = Column(String(100), nullable=True)
    manufacturer_name = Column(String(100), nullable=True)
    vendor_name = Column(String(100), nullable=True)
    os_name = Column(String(100), nullable=True)

    asset_type_id = Column(Integer, ForeignKey("asset_types.asset_type_id"), index=True)
    parent_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), index=True)
    location_id = Column(Integer, ForeignKey("locations.location_id"), index=True)

    # Аудит
    created_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    updated_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    model = relationship("AssetModel", back_populates="assets")
    asset_type = relationship("AssetType", back_populates="assets")
    asset_status = relationship("AssetStatus", lazy="select")
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

    creator = relationship("Employee", foreign_keys=[created_by])
    updater = relationship("Employee", foreign_keys=[updated_by])

    write_offs = relationship(
        "AssetWriteOff",
        back_populates="asset",
        cascade="all, delete-orphan",
        lazy="select"
    )

    asset_positions: Mapped[list["AssetPosition"]] = relationship(
        "AssetPosition",
        back_populates="asset",
        lazy="select",
        cascade="all, delete-orphan"
    )

    @computed_field
    @property
    def asset_type_name(self) -> Optional[str]:
        if self.asset_type:
            return self.asset_type.name
        return None

    # Обычные пользователи активов
    @computed_field
    @property
    def users(self) -> List[AssetUserResponse]:
        """Список обычных пользователей (type='user') с полной информацией о сотруднике"""
        result = []
        for a in self.assignments:
            if a.end_date is not None:
                continue  # Только активные привязки
            if a.assignment_type != "user":
                continue  # Только обычные пользователи

            emp = a.employee
            if not emp:
                continue

            # Формируем ФИО
            parts_ru = [p for p in [emp.last_name, emp.first_name, emp.middle_name] if p]
            parts_en = [p for p in [emp.last_name_en, emp.first_name_en, emp.middle_name_en] if p]

            result.append(AssetUserResponse(
                # Поля из Employee
                guid=emp.guid,
                # guid_person=emp.guid_person,
                employee_id=emp.employee_id,
                # last_name=emp.last_name,
                # first_name=emp.first_name,
                # middle_name=emp.middle_name,
                # last_name_en=emp.last_name_en,
                # first_name_en=emp.first_name_en,
                # middle_name_en=emp.middle_name_en,
                # birth_date=emp.birth_date,
                # employment_date=emp.employment_date,
                # dismissal_date=emp.dismissal_date,
                # phone=emp.phone,
                # email=emp.email,
                # position_guid=emp.position_guid,
                # department_guid=emp.department_guid,
                # created_at=emp.created_at,
                # updated_at=emp.updated_at,
                full_name_ru=" ".join(parts_ru) if parts_ru else None,
                full_name_en=" ".join(parts_en) if parts_en else None,
                # Поля из AssetAssignment
                start_date=a.start_date,
                end_date=a.end_date,
                assignment_type=a.assignment_type,
            ))
        return result

    # Ответственные пользователи активов
    @computed_field
    @property
    def responsible_users(self) -> List[AssetUserResponse]:
        """Список ответственных пользователей (type='responsible') с полной информацией о сотруднике"""
        result = []
        for a in self.assignments:
            if a.end_date is not None:
                continue  # Только активные привязки
            if a.assignment_type != "responsible":
                continue  # Только ответственные пользователи

            emp = a.employee
            if not emp:
                continue

            # Формируем ФИО
            parts_ru = [p for p in [emp.last_name, emp.first_name, emp.middle_name] if p]
            parts_en = [p for p in [emp.last_name_en, emp.first_name_en, emp.middle_name_en] if p]

            result.append(AssetUserResponse(
                # Поля из Employee
                guid=emp.guid,
                # guid_person=emp.guid_person,
                employee_id=emp.employee_id,
                # last_name=emp.last_name,
                # first_name=emp.first_name,
                # middle_name=emp.middle_name,
                # last_name_en=emp.last_name_en,
                # first_name_en=emp.first_name_en,
                # middle_name_en=emp.middle_name_en,
                # birth_date=emp.birth_date,
                # employment_date=emp.employment_date,
                # dismissal_date=emp.dismissal_date,
                # phone=emp.phone,
                # email=emp.email,
                # position_guid=emp.position_guid,
                # department_guid=emp.department_guid,
                # created_at=emp.created_at,
                # updated_at=emp.updated_at,
                full_name_ru=" ".join(parts_ru) if parts_ru else None,
                full_name_en=" ".join(parts_en) if parts_en else None,
                # Поля из AssetAssignment
                start_date=a.start_date,
                end_date=a.end_date,
                assignment_type=a.assignment_type,
            ))
        return result

    def __repr__(self):
        return f"<Asset(id={self.asset_id}, name={self.name})>"