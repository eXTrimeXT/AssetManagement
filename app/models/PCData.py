from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from app.models.Base import Base

class PCData(Base):
    __tablename__ = "pc_data"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    user = Column(JSONB, nullable=False)
    network = Column(JSONB, nullable=False)
    os = Column(JSONB, nullable=False)
    components = Column(JSONB, nullable=False)
    office_package = Column(JSONB, nullable=False)
    programs = Column(JSONB, nullable=False)