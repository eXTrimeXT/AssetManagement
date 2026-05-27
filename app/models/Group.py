from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, Mapped
from app.models.Base import Base

class Group(Base):
    """
    Модель группы.
    """
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    abbreviation = Column(String(50), nullable=False, unique=True, index=True)
    division_id = Column(Integer, ForeignKey("divisions.id"), nullable=False, index=True)

    # Связь
    division: Mapped["Division"] = relationship("Division", back_populates="groups")

    def __repr__(self):
        return f"<Group(id={self.id}, name='{self.name}', abbreviation='{self.abbreviation}')>"