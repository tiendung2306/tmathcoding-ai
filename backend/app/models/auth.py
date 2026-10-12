from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, SmallInteger, String

from app.core.dashboard_database import DashboardBase
from app.core.time import utc_now


class DashboardAccount(DashboardBase):
    __tablename__ = "dashboard_account"
    __table_args__ = (CheckConstraint("username = 'admin' AND role = 'admin' AND admin_slot = 1", name="single_admin"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False)
    admin_slot = Column(SmallInteger, unique=True, nullable=False)
    source_profile_id = Column(Integer, unique=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class DashboardAuthSession(DashboardBase):
    __tablename__ = "dashboard_auth_session"

    token_hash = Column(String(64), primary_key=True)
    account_id = Column(Integer, ForeignKey("dashboard_account.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
