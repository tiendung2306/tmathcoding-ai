from sqlalchemy import Column, Integer, String, DateTime
from app.core.dashboard_database import DashboardBase
from app.core.time import utc_now

class VirtualClassSession(DashboardBase):
    __tablename__ = "tmath_virtual_class_session"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    org_id = Column(Integer, index=True, nullable=False)
    name = Column(String(255), nullable=True) # e.g. "Phiên học 20/09"
    start_time = Column(DateTime, default=utc_now, index=True)
    end_time = Column(DateTime, nullable=True, index=True) # null means active
