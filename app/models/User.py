from typing import Optional, Dict

from pydantic import computed_field
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey
from datetime import datetime

from app.models.Base import Base
from app.models.Department import Department


class User(Base):
    """
    Модель пользователя (сотрудника компании).
    Хранит информацию о сотрудниках для назначения активов.
    """
    __tablename__ = "users"

    # Идентификаторы
    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_tab_id = Column(String(50), unique=True, index=True)   # Табельный номер

    # Имена
    owner = Column(String(150), nullable=True, index=True)      # ФИО на русском
    user_en_name = Column(String(150), nullable=True)           # ФИО на английском

    # Должность и отдел
    user_position = Column(String(100), nullable=True)          # Должность
    comment = Column(String(300), nullable=True)                # Комментарий

    # Департамент <- Отдел <- Группа
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    division_id = Column(Integer, ForeignKey("divisions.id"), nullable=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True, index=True)

    assets_admin = Column(Boolean, default=False, nullable=False)

    # Права пользователя из токена (UserDataJWT)
    permissions: Mapped[Optional[Dict[str, str]]] = mapped_column(JSON, default=dict, nullable=True)

    # Контакты
    email = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(50))

    # Системные поля
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Связь
    department: Mapped[Optional["Department"]] = relationship("Department", back_populates="users")
    division: Mapped[Optional["Division"]] = relationship("Division", back_populates="users")
    group: Mapped[Optional["Group"]] = relationship("Group", back_populates="users")

    def __repr__(self):
        return f"<User(id={self.user_id}, tab_id={self.user_tab_id}, owner={self.owner})>"

    @computed_field
    @property
    def department_abbreviation(self) -> Optional[str]:
        """Извлекает аббревиатуру департамента"""
        if self.department:
            return self.department.abbreviation
        return None

    @computed_field
    @property
    def division_abbreviation(self) -> Optional[str]:
        """Извлекает аббревиатуру отдела"""
        if self.division:
            return self.division.abbreviation
        return None

    @computed_field
    @property
    def group_abbreviation(self) -> Optional[str]:
        """Извлекает аббревиатуру группы"""
        if self.group:
            return self.group.abbreviation
        return None