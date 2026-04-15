from typing import Optional

from app.models.Base import Base
from sqlalchemy import Column, Integer, String, Date, Enum, ForeignKey, Text, DateTime, Boolean
from datetime import datetime
from sqlalchemy.orm import relationship, backref, Mapped


class Asset(Base):
    """
    Модель IT-актива (оборудования).
    Хранит информацию обо всех активах компании.
    """
    __tablename__ = "assets"

    # === Идентификаторы ===
    asset_id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # === Основные поля (из ТЗ) ===
    asset_status = Column(String(100), index=True, default="Приемка")           # Статус актива
    type_domain = Column(String(100))                                            # Тип домена
    asset_type_id = Column(Integer, ForeignKey("asset_types.asset_type_id"), index=True)    # Тип актива (ссылка на справочник)
    inventory_id = Column(String(50), unique=True, index=True)                  # Инвентарный номер
    affixed_inventory_id = Column(Boolean, default=False)                        # Инвентарный номер наклеен?
    info_storage_location = Column(String(200))                                  # Место хранения информации об активе

    # location = Column(String(150), nullable=True)                                             # Местоположение актива
    # В app/models/Asset.py
    location_id = Column(Integer, ForeignKey("locations.location_id"), index=True)
    location_obj: Mapped[Optional["Location"]] = relationship(
        "Location",
        back_populates="assets",
        lazy="joined" # Подгружаем локацию сразу при запросе актива
    )

    serial_number = Column(String(100), unique=True, index=True)                 # Серийный номер
    name = Column(String(150), nullable=False, index=True)                       # Имя актива
    passwork = Column(String(200))                                               # Строковое значение (пароль/ключ)
    date_issue = Column(Date)                                                    # Дата выдачи
    date_purchasing = Column(Date)                                               # Дата покупки
    comment = Column(Text)                                                       # Комментарий
    seller = Column(String(100))                                                 # Продавец
    price = Column(Integer, index=True)                                          # Цена

    # === Комплектация (иерархия через parent_id) ===
    parent_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), index=True)

    # === Служебные поля ===
    source = Column(String(100))                                                 # Источник поступления (поставщик)
    prepared_by = Column(Integer, ForeignKey("users.user_id"))                   # Подготовил (ответственный за документы)
    checked_by = Column(Integer, ForeignKey("users.user_id"))                    # Проверил (контроль документов)

    deleted_at = Column(DateTime, index=True)                                    # Soft delete
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # === Связи ===
    # Самореференция: комплектация (дочерние активы)
    parent = relationship(
        "Asset",
        remote_side=[asset_id],
        backref=backref(
            "children",
            lazy="selectin",
            cascade="all, delete-orphan"
        ),
        lazy="selectin"
    )

    # Связь с пользователями
    preparer = relationship("User", foreign_keys=[prepared_by])
    checker = relationship("User", foreign_keys=[checked_by])

    # Связь с software
    software_id = Column(Integer, ForeignKey("software.software_id", ondelete="SET NULL"), index=True)
    software = relationship("Software", back_populates="assets", lazy="joined")

    # Тип актива
    asset_type = relationship("AssetType", back_populates="assets", lazy="joined")

    def __repr__(self):
        return f"<Asset(id={self.asset_id}, name={self.name}, inventory_id={self.inventory_id})>"