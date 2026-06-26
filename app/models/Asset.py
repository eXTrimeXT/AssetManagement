from operator import index
from typing import Optional

from pydantic import computed_field

from app.models.Base import Base
from sqlalchemy import Column, Integer, String, Date, Enum, ForeignKey, Text, DateTime, Boolean
from datetime import datetime
from sqlalchemy.orm import relationship, backref, Mapped

from app.models.Software import Software


class Asset(Base):
    """
    Модель IT-актива (оборудования).
    Хранит информацию обо всех активах компании.
    """
    __tablename__ = "assets"

    # === Идентификаторы ===
    asset_id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # === Основные поля ===
    asset_status = Column(String(100), index=True, default="Приемка")               # Статус актива
    type_domain = Column(String(100))                                               # Тип домена
    model_id = Column(Integer, ForeignKey("asset_models.model_id"), index=True, nullable=True)  # Модель актива (ссылка на справочник)
    inventory_id = Column(String(100), unique=True, index=True)                     # Инвентарный номер
    affixed_inventory_id = Column(Boolean, default=False)                           # Инвентарный номер наклеен?
    info_storage_location = Column(String(200))                                     # Место хранения информации об активе


    serial_number = Column(String(100), unique=True, index=True, nullable=True)  # Серийный номер
    name = Column(String(150), nullable=False, index=True)                       # Имя актива
    date_issue = Column(Date)                                                    # Дата выдачи
    date_purchasing = Column(Date)                                               # Дата покупки
    comment = Column(Text)                                                       # Комментарий
    price = Column(Integer, index=True)                                          # Цена

    # === Комплектация (иерархия через parent_id) ===
    parent_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), index=True)

    # === Производитель и поставщик ===
    manufacturer_id = Column(Integer, ForeignKey("vendors.vendor_id"), index=True)
    manufacturer = relationship("Vendor", foreign_keys=[manufacturer_id], lazy="joined")

    vendor_id = Column(Integer, ForeignKey("vendors.vendor_id"), index=True)
    vendor = relationship("Vendor", foreign_keys=[vendor_id], lazy="joined")

    # === Служебные поля ===
    prepared_by = Column(Integer, ForeignKey("users.user_id"))                   # Подготовил
    checked_by = Column(Integer, ForeignKey("users.user_id"))                    # Проверил

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    preparer = relationship("User", foreign_keys=[prepared_by])
    checker = relationship("User", foreign_keys=[checked_by])

    software_id = Column(Integer, ForeignKey("software.software_id", ondelete="SET NULL"), index=True)
    software = relationship("Software", back_populates="assets", lazy="joined")

    # Модель актива (вместо AssetType)
    model = relationship("AssetModel", back_populates="assets", lazy="joined")

    # === Связи ===
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
    
    # === СКЛАД (вместо локации) ===
    warehouse_id = Column(Integer, ForeignKey("warehouses.warehouse_id"), index=True)
    warehouse_obj: Mapped[Optional["Warehouse"]] = relationship(
        "Warehouse",
        back_populates="assets",
        lazy="joined"  # Подгружаем склад сразу при запросе актива
    )

    # === ЦЕХ (для карты активов) ===
    workshop_id = Column(Integer, ForeignKey("workshops.workshop_id", ondelete="SET NULL"), index=True, nullable=True)
    workshop: Mapped[Optional["Workshop"]] = relationship(
        "Workshop",
        back_populates="assets",
        lazy="select"
    )

    # === СВЯЗЬ С ПОЗИЦИЯМИ НА КАРТЕ ===
    asset_positions: Mapped[list["AssetPosition"]] = relationship(
        "AssetPosition",
        back_populates="asset",
        lazy="select",
        cascade="all, delete-orphan"
    )

    # === Вычисляемые поля на основе связей ===
    @computed_field
    @property
    def asset_type_id(self) -> Optional[int]:
        if self.model and self.model.asset_class and self.model.asset_class.asset_type:
            # Берем ID типа (проверь точное имя поля в твоей модели AssetType: type_id, asset_type_id или id)
            return getattr(self.model.asset_class.asset_type, 'asset_type_id', None)
        return None

    @property
    def type_asset_en_name(self) -> Optional[str]:
        """Извлекает en_name типа актива через цепочку: model -> class -> type"""
        if self.model and self.model.asset_class and self.model.asset_class.asset_type:
            return self.model.asset_class.asset_type.en_name
        return None

    @property
    def type_asset_name(self) -> Optional[str]:
        """Извлекает name типа актива через цепочку: model -> class -> type"""
        if self.model and self.model.asset_class and self.model.asset_class.asset_type:
            return self.model.asset_class.asset_type.name
        return None

    @property
    def class_id(self) -> Optional[int]:
        if self.model and self.model.asset_class:
            # Берем ID типа (проверь точное имя поля в твоей модели AssetType: type_id, asset_type_id или id)
            return getattr(self.model.asset_class, 'class_id', None)
        return None

    @property
    def class_name(self) -> Optional[str]:
        """Извлекает en_name типа актива через цепочку: model -> class -> type"""
        if self.model and self.model.asset_class:
            return self.model.asset_class.class_name
        return None

    @computed_field
    @property
    def model_name(self) -> Optional[str]:
        return self.model.model_name if self.model else None

    @computed_field
    @property
    def warehouse_name(self) -> Optional[str]:
        # В твоей SQLAlchemy модели связь называется warehouse_obj
        return self.warehouse_obj.name if self.warehouse_obj else None

    @computed_field
    @property
    def parent_name(self) -> Optional[str]:
        return self.parent.name if self.parent else None

    @computed_field
    @property
    def software_office_type(self) -> Optional[str]:
        # Если в модели Software поле называется office_type
        return getattr(self.software, 'office_type', None) if self.software else None

    @computed_field
    @property
    def manufacturer_name(self) -> Optional[str]:
        return self.manufacturer.name if self.manufacturer else None

    @computed_field
    @property
    def vendor_name(self) -> Optional[str]:
        return self.vendor.name if self.vendor else None

    def __repr__(self):
        return f"<Asset(id={self.asset_id}, name={self.name}, inventory_id={self.inventory_id})>"