from typing import Optional, List

from pydantic import computed_field
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text, false, Boolean, func
from sqlalchemy.orm import relationship, backref, Mapped
from app.models.Base import Base
from app.schemas.assets.AssetAssignmentSchemas import AssetUserFullResponse
from app.schemas.assets.AssetSchemas import AssetLocationResponse
from app.models.assets.AssetAssignment import AssignmentTypeEnum


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
    # location_id = Column(Integer, ForeignKey("locations.location_id"), index=True)

    # Еженедельная проверка оборудования
    every_week_check = Column(Boolean, default=false)
    next_service = Column(Date)  # date
    service_period = Column(Integer, default=0) # Int (count days)

    # Аудит
    created_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    updated_by = Column(String(20), ForeignKey("zup_employees.employee_id"))
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

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
    # location = relationship("Location", back_populates="assets")

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

    # === Локация из AssetPosition + Workshop ===
    @computed_field
    @property
    def location(self) -> Optional[AssetLocationResponse]:
        """Текущая локация актива (активная позиция на карте)"""
        # Ищем активную позицию
        active_position = None
        for pos in (self.asset_positions or []):
            if pos.is_active:
                active_position = pos
                break

        if not active_position:
            return None

        workshop = active_position.workshop

        return AssetLocationResponse(
            workshop_id=workshop.workshop_id,
            place=active_position.place,
            level=active_position.level,
            x=active_position.x,
            y=active_position.y,
        )

    @computed_field
    @property
    def current_user(self):
        """Возвращает ОДНУ активную привязку текущего пользователя"""
        for assignment in self.assignments:
            if assignment.end_date is None and assignment.is_current:
                return assignment.employee_id
        return None

    @computed_field
    @property
    def users(self) -> List[AssetUserFullResponse]:
        """Список обычных пользователей с полной информацией"""
        result = []
        for a in self.assignments:
            if a.end_date is not None:
                continue
            if a.assignment_type != "user":
                continue
            emp = a.employee
            if not emp:
                continue

            parts_ru = [p for p in [emp.last_name, emp.first_name, emp.middle_name] if p]
            parts_en = [p for p in [emp.last_name_en, emp.first_name_en, emp.middle_name_en] if p]

            result.append(AssetUserFullResponse(
                # Базовые поля
                guid=emp.guid,
                employee_id=emp.employee_id,
                # last_name=emp.last_name,
                # first_name=emp.first_name,
                # middle_name=emp.middle_name,
                # last_name_en=emp.last_name_en,
                # first_name_en=emp.first_name_en,
                # middle_name_en=emp.middle_name_en,
                birth_date=emp.birth_date,
                employment_date=emp.employment_date,
                dismissal_date=emp.dismissal_date,
                phone=emp.phone,
                email=emp.email,
                comment=emp.comment,
                position_guid=emp.position_guid,
                department_guid=emp.department_guid,
                created_at=emp.created_at,
                updated_at=emp.updated_at,

                # Вычисляемые поля
                full_name_ru=" ".join(parts_ru) if parts_ru else None,
                full_name_en=" ".join(parts_en) if parts_en else None,

                # Поля из AssetAssignment
                start_date=a.start_date,
                end_date=a.end_date,
                assignment_type=a.assignment_type,
            ))
        return result

    @computed_field
    @property
    def responsible_users(self) -> List[AssetUserFullResponse]:
        """Список ответственных пользователей с полной информацией"""
        result = []
        for a in self.assignments:
            if a.end_date is not None:
                continue
            if a.assignment_type != "responsible":
                continue
            emp = a.employee
            if not emp:
                continue

            parts_ru = [p for p in [emp.last_name, emp.first_name, emp.middle_name] if p]
            parts_en = [p for p in [emp.last_name_en, emp.first_name_en, emp.middle_name_en] if p]

            result.append(AssetUserFullResponse(
                # Базовые поля
                guid=emp.guid,
                employee_id=emp.employee_id,
                # last_name=emp.last_name,
                # first_name=emp.first_name,
                # middle_name=emp.middle_name,
                # last_name_en=emp.last_name_en,
                # first_name_en=emp.first_name_en,
                # middle_name_en=emp.middle_name_en,
                birth_date=emp.birth_date,
                employment_date=emp.employment_date,
                dismissal_date=emp.dismissal_date,
                phone=emp.phone,
                email=emp.email,
                comment=emp.comment,
                position_guid=emp.position_guid,
                department_guid=emp.department_guid,
                created_at=emp.created_at,
                updated_at=emp.updated_at,

                # Вычисляемые поля
                full_name_ru=" ".join(parts_ru) if parts_ru else None,
                full_name_en=" ".join(parts_en) if parts_en else None,

                # Поля из AssetAssignment
                start_date=a.start_date,
                end_date=a.end_date,
                assignment_type=a.assignment_type,
            ))
        return result

    @computed_field
    @property
    def serving_users(self) -> List[AssetUserFullResponse]:
        """Список обслуживающих пользователей с полной информацией"""
        result = []
        for a in self.assignments:
            if a.end_date is not None:
                continue
            if a.assignment_type != AssignmentTypeEnum.SERVING:
                continue
            emp = a.employee
            if not emp:
                continue

            parts_ru = [p for p in [emp.last_name, emp.first_name, emp.middle_name] if p]
            parts_en = [p for p in [emp.last_name_en, emp.first_name_en, emp.middle_name_en] if p]

            result.append(AssetUserFullResponse(
                # Базовые поля
                guid=emp.guid,
                employee_id=emp.employee_id,
                # last_name=emp.last_name,
                # first_name=emp.first_name,
                # middle_name=emp.middle_name,
                # last_name_en=emp.last_name_en,
                # first_name_en=emp.first_name_en,
                # middle_name_en=emp.middle_name_en,
                birth_date=emp.birth_date,
                employment_date=emp.employment_date,
                dismissal_date=emp.dismissal_date,
                phone=emp.phone,
                email=emp.email,
                comment=emp.comment,
                position_guid=emp.position_guid,
                department_guid=emp.department_guid,
                created_at=emp.created_at,
                updated_at=emp.updated_at,

                # Вычисляемые поля
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