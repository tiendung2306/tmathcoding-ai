from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from app.core.database import Base

class VirtualClassSession(Base):
    __tablename__ = "tmath_virtual_class_session"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    org_id = Column(Integer, ForeignKey("judge_organization.id"), index=True, nullable=False)
    name = Column(String(255), nullable=True) # e.g. "Phiên học 20/09"
    start_time = Column(DateTime, default=datetime.utcnow, index=True)
    end_time = Column(DateTime, nullable=True, index=True) # null means active
