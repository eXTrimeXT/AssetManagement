from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from app.models.Base import Base

class AndroidData(Base):
    __tablename__ = "android_data"

    id = Column(Integer, primary_key=True, index=True)
    serial_number = Column(String(50), unique=True, nullable=False, index=True)
    request_time = Column(String(50))
    device = Column(JSONB, nullable=False)
    system = Column(JSONB, nullable=False)
    hardware = Column(JSONB, nullable=False)
    network = Column(JSONB, nullable=False)
    battery = Column(JSONB, nullable=False)